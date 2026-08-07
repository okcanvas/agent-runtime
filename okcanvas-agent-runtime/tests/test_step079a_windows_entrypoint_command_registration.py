from __future__ import annotations

from pathlib import Path

from scripts import windows_entrypoint


def test_step079_live_command_is_registered_and_routes_to_live_script(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        windows_entrypoint,
        "load_local_environment",
        lambda root=windows_entrypoint.ROOT: ({"OPENAI_API_KEY": "test-key", "OKCANVAS_AGENT_MODEL": "gpt-4.1"}, None),
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

    assert windows_entrypoint.run(["atomic-task-run-ownership-transfer-live-acceptance"]) == 0
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == windows_entrypoint.sys.executable
    assert command[1] == str(windows_entrypoint.ROOT / "scripts" / "run_step079a_live_acceptance.py")
    assert captured["cwd"] == windows_entrypoint.ROOT
    assert captured["check"] is False
    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["OKCANVAS_STEP079_LIVE_ACCEPTANCE"] == "1"
    assert environment["OKCANVAS_STEP079A_LIVE_ACCEPTANCE"] == "1"
    assert environment["OPENAI_API_KEY"] == "test-key"
    assert environment["OKCANVAS_AGENT_MODEL"] == "gpt-4.1"


def test_step079_launcher_command_is_present_in_parser_choices() -> None:
    parser = windows_entrypoint._parser()
    command_action = next(action for action in parser._actions if action.dest == "command")
    assert "atomic-task-run-ownership-transfer-live-acceptance" in command_action.choices


def test_step079_live_launcher_and_entrypoint_are_aligned() -> None:
    launcher = (windows_entrypoint.ROOT / "sh_run_step079_live_acceptance.cmd").read_text(encoding="utf-8")
    source = (windows_entrypoint.ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    command = "atomic-task-run-ownership-transfer-live-acceptance"
    assert command in launcher
    assert command in source
    assert "run_step079a_live_acceptance.py" in source
