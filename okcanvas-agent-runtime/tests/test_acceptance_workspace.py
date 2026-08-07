from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
import okcanvas_agent_runtime.support.acceptance.workspace as workspace_module


def test_pass_exports_compact_evidence_then_removes_workspace(tmp_path: Path) -> None:
    output = tmp_path / "evidence" / "summary.json"
    workspace = AcceptanceWorkspace(
        step_id="STEPTEST",
        output=output,
        base_dir=tmp_path / "work",
        acceptance_id="pass-case",
    )
    root = workspace.root
    (workspace.database_dir / "acceptance.sqlite3").write_bytes(b"db")
    final = workspace.finalize({"schema_version": "test-v1", "state": "PASSED"})

    assert not root.exists()
    assert output.is_file()
    assert final["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert final["acceptance_workspace"]["preserved_path"] is None
    assert final["acceptance_workspace"]["product_runtime_state"] is False
    assert json.loads(output.read_text(encoding="utf-8")) == final


def test_failed_acceptance_preserves_exact_workspace_path(tmp_path: Path) -> None:
    output = tmp_path / "evidence" / "summary.json"
    workspace = AcceptanceWorkspace(
        step_id="STEPTEST",
        output=output,
        base_dir=tmp_path / "work",
        acceptance_id="failed-case",
    )
    final = workspace.finalize({"schema_version": "test-v1", "state": "FAILED"})

    assert workspace.root.is_dir()
    assert final["acceptance_workspace"]["cleanup_state"] == "PRESERVED"
    assert final["acceptance_workspace"]["preserved_path"] == str(workspace.root)
    assert (workspace.evidence_dir / "acceptance-summary.json").is_file()
    shutil.rmtree(workspace.root)


def test_resources_close_in_reverse_order_before_cleanup(tmp_path: Path) -> None:
    actions: list[str] = []

    class ObservedWorkspace(AcceptanceWorkspace):
        def _remove_tree(self):
            actions.append("cleanup")
            return super()._remove_tree()

    workspace = ObservedWorkspace(
        step_id="STEPTEST",
        output=tmp_path / "summary.json",
        base_dir=tmp_path / "work",
        acceptance_id="close-order",
    )
    workspace.register_closer("first", lambda: actions.append("first"))
    workspace.register_closer("second", lambda: actions.append("second"))
    final = workspace.finalize({"state": "PASSED"})

    assert actions == ["second", "first", "cleanup"]
    assert final["acceptance_workspace"]["resources_closed"] is True


def test_cleanup_retry_is_bounded_and_happens_after_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real_rmtree = workspace_module.shutil.rmtree

    def flaky_rmtree(path: Path, *, ignore_errors: bool = False) -> None:
        calls.append("cleanup")
        if calls.count("cleanup") == 1:
            raise PermissionError("simulated Windows lock")
        real_rmtree(path, ignore_errors=ignore_errors)

    monkeypatch.setattr(workspace_module.shutil, "rmtree", flaky_rmtree)
    workspace = AcceptanceWorkspace(
        step_id="STEPTEST",
        output=tmp_path / "summary.json",
        base_dir=tmp_path / "work",
        acceptance_id="retry-case",
        cleanup_attempts=2,
        cleanup_delay_seconds=0,
    )
    workspace.register_closer("database", lambda: calls.append("close"))
    final = workspace.finalize({"state": "PASSED"})

    assert calls == ["close", "cleanup", "cleanup"]
    assert final["acceptance_workspace"]["cleanup_attempts"] == 2
    assert final["acceptance_workspace"]["cleanup_state"] == "COMPLETED"


def test_close_failure_preserves_workspace_without_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cleanup_called = False
    real_rmtree = workspace_module.shutil.rmtree

    def fail_if_called(*_args, **_kwargs):
        nonlocal cleanup_called
        cleanup_called = True
        raise AssertionError("cleanup must not run after resource close failure")

    monkeypatch.setattr(workspace_module.shutil, "rmtree", fail_if_called)
    workspace = AcceptanceWorkspace(
        step_id="STEPTEST",
        output=tmp_path / "summary.json",
        base_dir=tmp_path / "work",
        acceptance_id="close-failure",
    )

    def fail_close() -> None:
        raise RuntimeError("still open")

    workspace.register_closer("database", fail_close)
    final = workspace.finalize({"state": "PASSED"})

    assert cleanup_called is False
    assert final["state"] == "FAILED"
    assert final["state_before_resource_close"] == "PASSED"
    assert final["acceptance_workspace"]["cleanup_state"] == "PRESERVED"
    assert workspace.root.exists()
    real_rmtree(workspace.root)


def test_context_exception_preserves_diagnostic_workspace(tmp_path: Path) -> None:
    output = tmp_path / "summary.json"
    workspace: AcceptanceWorkspace | None = None
    with pytest.raises(RuntimeError, match="fixture failure"):
        with AcceptanceWorkspace(
            step_id="STEPTEST",
            output=output,
            base_dir=tmp_path / "work",
            acceptance_id="exception-case",
        ) as current:
            workspace = current
            raise RuntimeError("fixture failure")

    assert workspace is not None
    assert workspace.root.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["state"] == "FAILED"
    assert payload["acceptance_workspace"]["preserved_path"] == str(workspace.root)
    shutil.rmtree(workspace.root)
