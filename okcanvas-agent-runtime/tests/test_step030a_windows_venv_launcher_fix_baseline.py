from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts import windows_entrypoint

ROOT = Path(__file__).resolve().parents[1]


def test_step030a_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.windows_project_venv_launcher_enforced is True
    assert info.step030_windows_venv_launcher_fix_implemented is True
    assert info.step030_windows_venv_launcher_deterministic_accepted is True
    assert info.step030_windows_venv_launcher_live_accepted is True
    assert info.commerce_snapshot_non_empty_inventory_windows_live_accepted is True


def test_step030a_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP030A_ACCEPTANCE.json").read_text(encoding="utf-8")
    )
    assert payload["state"] == "PASSED"
    assert len(payload["checks"]) == 8
    assert all(payload["checks"].values())
    assert payload["launcher_violations"] == []
    assert payload["fixed_launcher"] == "sh_run_step030_acceptance.cmd"
    assert payload["windows_live_rerun_pending"] is False
    assert payload["windows_live_accepted"] is True


def test_windows_entrypoint_routes_step030a_acceptance(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        windows_entrypoint,
        "load_local_environment",
        lambda root=windows_entrypoint.ROOT: ({}, None),
    )

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["check"] = check

        class Completed:
            returncode = 0

        return Completed()

    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["windows-venv-launcher-acceptance"]) == 0
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == windows_entrypoint.sys.executable
    assert str(ROOT / "scripts" / "run_step030a_acceptance.py") in command
