from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import read_component_source
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts import windows_entrypoint

ROOT = Path(__file__).resolve().parents[1]


def test_step035_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.orphaned_running_run_windows_live_accepted is True
    assert info.terminal_outcome_reconciliation_implemented is True
    assert (
        info.terminal_outcome_reconciliation_mode
        == "explicit-local-operator-retention-only-no-reexecution"
    )
    assert info.terminal_outcome_success_payload_deleted is True
    assert info.terminal_outcome_failure_cancel_payload_retained is True
    assert info.terminal_outcome_reconciliation_replay_noop is True
    assert info.terminal_outcome_reconciliation_deterministic_accepted is True
    assert info.terminal_outcome_reconciliation_windows_live_accepted is True


def test_step035_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP035_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert len(payload["checks"]) == 21
    assert all(payload["checks"].values())
    assert payload["reconciliation"]["scanned"] == 3
    assert payload["reconciliation"]["reconciled"] == 3
    assert payload["reconciliation"]["deleted"] == 1
    assert payload["reconciliation"]["retained"] == 2
    assert payload["gateway_call_count"] == 0
    assert payload["protected_payload_file_count"] == 2
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"


def test_step035_runtime_has_no_reexecution_path() -> None:
    lifecycle = read_component_source(ROOT, "run_submission.lifecycle")
    app = read_component_source(ROOT, "control_api.app")
    assert "reconcile_terminal_outcomes" in lifecycle
    assert "/v1/run-submissions/reconcile-terminal-outcomes" in app
    assert "schedule_prepared" not in lifecycle
    assert "gateway.run" not in lifecycle


def test_windows_entrypoint_routes_step035_acceptance(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        windows_entrypoint,
        "load_local_environment",
        lambda root=windows_entrypoint.ROOT: ({}, None),
    )

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command

        class Completed:
            returncode = 0

        return Completed()

    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["terminal-outcome-reconciliation-acceptance"]) == 0
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == windows_entrypoint.sys.executable
    assert str(ROOT / "scripts" / "run_step035_acceptance.py") in command


def test_step035_windows_launcher_uses_project_venv() -> None:
    launcher = (ROOT / "sh_run_step035_acceptance.cmd").read_text(encoding="utf-8")
    assert 'if not exist ".venv\\Scripts\\python.exe"' in launcher
    assert (
        '".venv\\Scripts\\python.exe" scripts\\windows_entrypoint.py '
        "terminal-outcome-reconciliation-acceptance %*"
    ) in launcher
    assert "\npython " not in launcher.lower()
