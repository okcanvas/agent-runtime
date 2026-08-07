from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import windows_entrypoint
from scripts.validate_acceptance_launcher_registry import validate

ROOT = Path(__file__).resolve().parents[1]
COMMAND = "root-package-architecture-live-acceptance"


def test_step081_windows_live_command_is_registered_and_dispatched(monkeypatch) -> None:
    action = next(item for item in windows_entrypoint._parser()._actions if item.dest == "command")
    assert COMMAND in action.choices
    assert windows_entrypoint._parser().parse_args([COMMAND]).command == COMMAND
    captured: dict[str, object] = {}

    def fake_run(command, *, cwd, env, check):
        captured.update(command=command, cwd=cwd, env=env, check=check)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", lambda: ({}, None))
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run([COMMAND]) == 0
    command = captured["command"]
    assert command[0] == windows_entrypoint.sys.executable
    assert command[1] == str(ROOT / "scripts/run_step081d_live_acceptance.py")
    assert captured["cwd"] == ROOT
    assert captured["env"]["OKCANVAS_STEP081_LIVE_ACCEPTANCE"] == "1"
    assert captured["env"]["OKCANVAS_STEP081C_LIVE_ACCEPTANCE"] == "1"


def test_step081_launchers_use_project_venv_and_bytecode_isolation() -> None:
    deterministic = (ROOT / "sh_run_step081_acceptance.cmd").read_text(encoding="utf-8")
    live = (ROOT / "sh_run_step081_live_acceptance.cmd").read_text(encoding="utf-8")
    assert r'.venv\Scripts\python.exe' in deterministic
    assert "python_bytecode_isolation.py" in deterministic
    assert "run_step081_acceptance.py" in deterministic
    assert r'.venv\Scripts\python.exe' in live
    assert "python_bytecode_isolation.py" in live
    assert "windows_entrypoint.py root-package-architecture-live-acceptance" in live


def test_step081_launcher_registry_is_complete_and_current() -> None:
    result = validate()
    assert result["state"] == "PASSED"
    assert result["passed_checks"] == result["total_checks"] == 7
    assert result["script_count"] == len(list((ROOT / "scripts").glob("run_step*_acceptance.py")))
    assert result["launcher_count"] == len(list(ROOT.glob("sh_run_step*_acceptance.cmd")))
    assert result["record_count"] == result["script_count"] + result["launcher_count"]
    payload = json.loads((ROOT / "specs/acceptance/launcher-registry.json").read_text())
    required = {(item["kind"], item["mode"]) for item in payload["required_current_records"]}
    current_records = [item for item in payload["records"] if item["classification"] == "CURRENT"]
    current = {item["path"] for item in current_records}
    assert result["current_record_count"] == len(required) == len(current_records)
    assert {(item["kind"], item["mode"]) for item in current_records} == required
    token = payload["current_step_token"].casefold()
    assert all(token in path.casefold() for path in current)
