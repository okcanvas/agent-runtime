from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import windows_entrypoint

ROOT = Path(__file__).resolve().parents[1]
COMMAND = "architecture-constitution-live-acceptance"


def test_architecture_constitution_live_command_is_registered_and_dispatched(monkeypatch) -> None:
    action = next(
        item for item in windows_entrypoint._parser()._actions if item.dest == "command"
    )
    assert COMMAND in action.choices
    assert windows_entrypoint._parser().parse_args([COMMAND]).command == COMMAND

    captured: dict[str, object] = {}

    def fake_run(command, *, cwd, env, check):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["check"] = check
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", lambda: ({}, None))
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run([COMMAND]) == 0

    command = captured["command"]
    assert command[0] == windows_entrypoint.sys.executable
    assert command[1] == str(ROOT / "scripts/run_step080a_live_acceptance.py")
    assert captured["cwd"] == ROOT
    environment = captured["env"]
    assert environment["OKCANVAS_STEP080_LIVE_ACCEPTANCE"] == "1"
    assert environment["OKCANVAS_STEP080A_LIVE_ACCEPTANCE"] == "1"


def test_step080a_launchers_use_project_venv_and_isolation() -> None:
    deterministic = (ROOT / "sh_run_step080a_acceptance.cmd").read_text(encoding="utf-8")
    live = (ROOT / "sh_run_step080a_live_acceptance.cmd").read_text(encoding="utf-8")
    assert r'.venv\Scripts\python.exe' in deterministic
    assert "python_bytecode_isolation.py" in deterministic
    assert "run_step080a_acceptance.py" in deterministic
    assert r'.venv\Scripts\python.exe' in live
    assert "python_bytecode_isolation.py" in live
    assert "windows_entrypoint.py architecture-constitution-live-acceptance" in live
