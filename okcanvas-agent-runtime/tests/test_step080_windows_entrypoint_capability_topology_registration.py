from __future__ import annotations

from scripts import windows_entrypoint

COMMAND = "capability-topology-live-acceptance"


def test_step080_live_command_is_registered_and_routes_to_live_script(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        windows_entrypoint,
        "load_local_environment",
        lambda root=windows_entrypoint.ROOT: (
            {"OPENAI_API_KEY": "test-key", "OKCANVAS_AGENT_MODEL": "gpt-4.1"},
            None,
        ),
    )

    def fake_run(command, *, cwd, env, check):
        captured.update(command=command, cwd=cwd, env=env, check=check)

        class Completed:
            returncode = 0

        return Completed()

    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run([COMMAND]) == 0
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == windows_entrypoint.sys.executable
    assert command[1] == str(windows_entrypoint.ROOT / "scripts/run_step080_live_acceptance.py")
    assert captured["cwd"] == windows_entrypoint.ROOT
    assert captured["check"] is False
    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["OKCANVAS_STEP080_LIVE_ACCEPTANCE"] == "1"
    assert environment["OPENAI_API_KEY"] == "test-key"
    assert environment["OKCANVAS_AGENT_MODEL"] == "gpt-4.1"


def test_step080_live_command_parser_launcher_and_dispatch_are_aligned() -> None:
    parser = windows_entrypoint._parser()
    action = next(item for item in parser._actions if item.dest == "command")
    assert COMMAND in action.choices
    launcher = (windows_entrypoint.ROOT / "sh_run_step080_live_acceptance.cmd").read_text(
        encoding="utf-8"
    )
    source = (windows_entrypoint.ROOT / "scripts/windows_entrypoint.py").read_text(
        encoding="utf-8"
    )
    assert COMMAND in launcher
    assert f'args.command == "{COMMAND}"' in source
    assert "run_step080_live_acceptance.py" in source


def test_step080_live_contract_has_61_base_checks_plus_api_key_check() -> None:
    import ast

    source = (windows_entrypoint.ROOT / "scripts/run_step080_live_acceptance.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    check_counts = [
        len(node.value.keys)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "checks" for target in node.targets)
        and isinstance(node.value, ast.Dict)
    ]
    assert check_counts == [61]
    assert 'payload["checks"]["api_key_not_in_summary"]' in source
