from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import read_component_source
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts import windows_entrypoint

ROOT = Path(__file__).resolve().parents[1]


def test_step036_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.terminal_outcome_reconciliation_windows_live_accepted is True
    assert info.recorded_run_runtime_binding_verification_implemented is True
    assert info.recorded_run_runtime_binding_event_required is True
    assert info.recorded_run_runtime_binding_current_catalog_verified is True
    assert info.recorded_run_runtime_binding_persisted_with_evaluation is True
    assert info.recorded_run_unbound_legacy_evaluation_fails_closed is True
    assert info.recorded_run_runtime_binding_verification_deterministic_accepted is True
    assert info.recorded_run_runtime_binding_verification_windows_live_accepted is True


def test_step036_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP036_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert len(payload["checks"]) == 18
    assert all(payload["checks"].values())
    assert payload["gateway_call_count"] == 3
    assert payload["evaluation_count"] == 1
    assert payload["artifact_count"] == 3
    assert payload["tampered_recorded_binding"]["code"] == "RUNTIME_BINDING_DRIFT"
    assert payload["current_runtime_drift"]["code"] == "RUNTIME_BINDING_DRIFT"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"


def test_step036_evaluation_service_resolves_current_runtime_binding() -> None:
    source = read_component_source(ROOT, "evaluation.application")
    assert "RuntimeBindingResolver" in source
    assert "self._runtime_bindings.resolve" in source
    assert "RUNTIME_BINDING_DRIFT" in source
    assert '"runtime_binding_sha256": runtime_binding.runtime_binding_sha256' in source


def test_windows_entrypoint_routes_step036_acceptance(monkeypatch) -> None:
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
    assert windows_entrypoint.run(["recorded-runtime-binding-evaluation-acceptance"]) == 0
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == windows_entrypoint.sys.executable
    assert str(ROOT / "scripts" / "run_step036_acceptance.py") in command


def test_step036_windows_launcher_uses_project_venv() -> None:
    launcher = (ROOT / "sh_run_step036_acceptance.cmd").read_text(encoding="utf-8")
    assert 'if not exist ".venv\\Scripts\\python.exe"' in launcher
    assert (
        '".venv\\Scripts\\python.exe" scripts\\windows_entrypoint.py '
        "recorded-runtime-binding-evaluation-acceptance %*"
    ) in launcher
    assert "\npython " not in launcher.lower()
