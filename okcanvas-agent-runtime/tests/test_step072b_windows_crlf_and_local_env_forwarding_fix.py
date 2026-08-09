from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.package_source import DEFAULT_OUTPUT
from scripts import windows_entrypoint
from scripts.python_bytecode_isolation import ENV_NAME

ROOT = Path(__file__).resolve().parents[1]


def test_current_baseline_and_windows_gate_are_exact() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.openai_trace_export_windows_live_accepted is True
    assert info.windows_pycache_overlay_isolation_implemented is True
    assert info.windows_pycache_overlay_isolation_windows_accepted is True
    assert info.windows_crlf_collision_regression_fixed is True
    assert info.windows_local_environment_forwarding_implemented is True
    assert (
        info.windows_local_environment_forwarding_mode
        == "data-only-loader-through-isolated-entrypoint"
    )
    assert info.windows_crlf_and_local_env_fix_deterministic_accepted is True
    assert info.windows_crlf_and_local_env_fix_windows_accepted is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


def test_step072a_windows_failures_are_recorded_exactly() -> None:
    evidence = json.loads(
        (ROOT / "docs/evidence/STEP072A_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["schema_version"] == "okcanvas-step072a-windows-acceptance-summary-v1"
    assert evidence["deterministic"]["state"] == "FAILED"
    assert evidence["deterministic"]["passed_checks"] == 23
    assert evidence["deterministic"]["total_checks"] == 24
    assert evidence["deterministic"]["failed_checks"] == ["focused_step072a_tests_pass"]
    assert evidence["deterministic"]["failure_class"] == "windows-text-newline-translation"
    assert evidence["live"]["state"] == "FAILED"
    assert evidence["live"]["passed_checks"] == 5
    assert evidence["live"]["total_checks"] == 15
    assert evidence["live"]["readiness_issue_codes"] == [
        "OPENAI_API_KEY_MISSING",
        "OKCANVAS_AGENT_MODEL_MISSING",
    ]
    assert evidence["live"]["bytecode_isolation_environment_present"] is True
    assert evidence["live"]["bytecode_isolation_active_in_interpreter"] is True
    assert evidence["live"]["bytecode_isolation_prefix_outside_project"] is True
    assert evidence["live"]["failure_class"] == "local-environment-loader-bypassed"


def test_collision_fixture_writes_exact_bytes_cross_platform() -> None:
    source = (ROOT / "tests/test_step072a_windows_pycache_overlay_isolation_fix.py").read_text(
        encoding="utf-8"
    )
    assert 'module.write_bytes(old_source.encode("utf-8"))' in source
    assert 'module.write_bytes(new_source.encode("utf-8"))' in source
    assert 'module.write_text(old_source' not in source
    assert 'module.write_text(new_source' not in source


def test_data_only_entrypoint_forwards_local_environment_and_pycache(monkeypatch) -> None:
    captured: dict[str, object] = {}
    prefix = ROOT.parent / "temporary-pycache-probe"

    def fake_load(root=windows_entrypoint.ROOT):
        return {
            "OPENAI_API_KEY": "step072b-secret",
            "OKCANVAS_AGENT_MODEL": "gpt-4.1",
        }, None

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setenv(ENV_NAME, str(prefix))
    monkeypatch.setattr(windows_entrypoint, "load_local_environment", fake_load)
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["windows-crlf-local-env-live-acceptance"]) == 0
    assert str(ROOT / "scripts/run_step072b_live_acceptance.py") in captured["command"]
    assert captured["env"]["OPENAI_API_KEY"] == "step072b-secret"
    assert captured["env"]["OKCANVAS_AGENT_MODEL"] == "gpt-4.1"
    assert captured["env"][ENV_NAME] == str(prefix)
    assert "step072b-secret" not in " ".join(str(item) for item in captured["command"])


def test_step072a_and_step072b_live_launchers_use_isolated_data_loader() -> None:
    expected = {
        "sh_run_step072a_live_acceptance.cmd": (
            "scripts\\python_bytecode_isolation.py scripts\\windows_entrypoint.py "
            "windows-pycache-overlay-live-acceptance"
        ),
        "sh_run_step072b_live_acceptance.cmd": (
            "scripts\\python_bytecode_isolation.py scripts\\windows_entrypoint.py "
            "windows-crlf-local-env-live-acceptance"
        ),
        "sh_run_step072b_acceptance.cmd": (
            "scripts\\python_bytecode_isolation.py scripts\\run_step072b_acceptance.py"
        ),
    }
    for relative, fragment in expected.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert fragment in source
        assert ".venv\\Scripts\\python.exe" in source


def test_live_evidence_and_package_are_local_only() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    packaging_policy = (ROOT / "scripts/step081_product_inventory.py").read_text(encoding="utf-8")
    package_source = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    assert "docs/evidence/step072b-live/" in gitignore
    assert '("docs", "evidence", "step072b-live")' in packaging_policy
    assert DEFAULT_OUTPUT.name in package_source

def test_windows_launcher_portability_constitution_and_live_closure_are_exact() -> None:
    document = (ROOT / "docs/38-WINDOWS-PYTHON-LAUNCHER-PORTABILITY.md").read_text(
        encoding="utf-8"
    )
    evidence = json.loads(
        (ROOT / "docs/evidence/STEP072B_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "stale timestamp-and-size bytecode collision" in document
    assert "Path.write_bytes" in document
    assert "python_bytecode_isolation.py" in document
    assert "windows_entrypoint.py" in document
    assert "New Windows launcher review checklist" in document
    assert "docs/38-WINDOWS-PYTHON-LAUNCHER-PORTABILITY.md" in agents
    assert evidence["state"] == "WINDOWS_LIVE_ACCEPTED"
    assert evidence["deterministic"]["passed_checks"] == 24
    assert evidence["live"]["passed_checks"] == 17
    assert evidence["live"]["model_calls"] == 1
    assert evidence["live"]["terminal_status"] == "SUCCEEDED"
    assert evidence["live"]["python_pycache_prefix_active"] is True
    assert evidence["live"]["python_pycache_prefix_inside_project"] is False
    assert evidence["live"]["local_environment_forwarded_to_current_interpreter"] is True
    assert evidence["live"]["trace_error_markers"] == []
    assert evidence["security"]["api_key_value_recorded"] is False
    assert evidence["security"]["api_key_persisted"] is False
    assert evidence["security"]["raw_attachment_persisted"] is False
    assert evidence["security"]["workspace_cleanup_completed"] is True

