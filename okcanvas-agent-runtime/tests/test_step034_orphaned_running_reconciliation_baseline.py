from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import read_component_source
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts import windows_entrypoint

ROOT = Path(__file__).resolve().parents[1]


def test_step034_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.agent_runtime_binding_windows_live_accepted is True
    assert info.active_run_restart_recovery_implemented is False
    assert info.orphaned_running_run_reconciliation_implemented is True
    assert (
        info.orphaned_running_run_reconciliation_mode
        == "explicit-local-operator-fail-without-reexecution"
    )
    assert info.orphaned_running_run_generation_fence_implemented is True
    assert info.orphaned_running_run_late_event_fenced is True
    assert info.orphaned_running_run_late_metadata_fenced is True
    assert info.orphaned_running_run_late_artifact_fenced is True
    assert info.orphaned_running_run_failure_code == "PROCESS_LOSS_RECONCILED"
    assert info.orphaned_running_run_deterministic_accepted is True
    assert info.orphaned_running_run_windows_live_accepted is True


def test_step034_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP034_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert len(payload["checks"]) == 20
    assert all(payload["checks"].values())
    assert payload["reconciliation"]["scanned"] == 1
    assert payload["reconciliation"]["reconciled"] == 1
    assert payload["failure"]["code"] == "PROCESS_LOSS_RECONCILED"
    assert payload["failure"]["retryable"] is False
    assert payload["gateway_call_count"] == 0
    assert payload["final_counts"]["artifacts"] == 0
    assert payload["final_counts"]["evaluations"] == 0
    assert payload["protected_payload_file_count"] == 1
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"


def test_step034_windows_live_evidence_is_closed() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP034_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["checks_passed"] == 20
    assert payload["checks_total"] == 20
    assert payload["reconciliation"]["reconciled"] == 1
    assert payload["failure"]["code"] == "PROCESS_LOSS_RECONCILED"
    assert payload["gateway_call_count"] == 0
    assert payload["cleanup_state"] == "COMPLETED"


def test_step034_is_explicit_reconciliation_not_sdk_resume() -> None:
    execution = read_component_source(ROOT, "run_submission.execution")
    store = read_component_source(ROOT, "run_submission.store")
    policy = json.loads(
        (ROOT / "specs" / "submissions" / "governed-execution-lifecycle-policy.json").read_text(
            encoding="utf-8"
        )
    )
    assert "reconcile_orphaned_running" in execution
    assert "reconcile_orphaned_running" in store
    assert '"PROCESS_LOSS_RECONCILED"' in store
    assert '"reexecution_attempted": False' in store
    assert policy["active_running_run_recovery_enabled"] is False
    assert policy["distributed_worker_lease_enabled"] is False


def test_windows_entrypoint_routes_step034_acceptance(monkeypatch) -> None:
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
    assert windows_entrypoint.run(["orphaned-running-reconciliation-acceptance"]) == 0
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == windows_entrypoint.sys.executable
    assert str(ROOT / "scripts" / "run_step034_acceptance.py") in command


def test_step034_windows_launcher_uses_project_venv() -> None:
    launcher = (ROOT / "sh_run_step034_acceptance.cmd").read_text(encoding="utf-8")
    assert 'if not exist ".venv\\Scripts\\python.exe"' in launcher
    assert (
        '".venv\\Scripts\\python.exe" scripts\\windows_entrypoint.py '
        "orphaned-running-reconciliation-acceptance %*"
    ) in launcher
    assert "\npython " not in launcher.lower()
