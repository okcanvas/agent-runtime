from __future__ import annotations

import subprocess

from okcanvas_agent_runtime import cli
from scripts import windows_entrypoint


class _FakeClient:
    def __init__(self, config) -> None:
        self.config = config

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def list_approvals(self, **kwargs):
        return {"schema_version": "okcanvas-local-approval-operator-list-v1", "approvals": []}

    def decide(self, **kwargs):
        return {"schema_version": "okcanvas-control-tool-approval-resume-v1", "state": "SUCCEEDED"}


def test_approval_operator_cli_commands(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ApprovalOperatorConfig, "from_env", lambda **kwargs: object())
    monkeypatch.setattr(cli, "LocalApprovalOperatorClient", _FakeClient)

    assert cli.main(["approval-inbox-list", "--pretty"]) == 0
    assert "okcanvas-local-approval-operator-list-v1" in capsys.readouterr().out

    assert cli.main(
        [
            "approval-decide",
            "--approval-id",
            "approval_1",
            "--decision",
            "APPROVE",
            "--confirmation",
            "APPROVE approval_1 run_1",
        ]
    ) == 0
    assert '"state": "SUCCEEDED"' in capsys.readouterr().out


def test_windows_entrypoint_routes_approval_operator(monkeypatch) -> None:
    captured: list[list[str]] = []

    monkeypatch.setattr(
        windows_entrypoint,
        "load_local_environment",
        lambda root=windows_entrypoint.ROOT: ({"OKCANVAS_CONTROL_ADMIN_KEY": "a" * 16}, None),
    )

    def fake_run(command, *, cwd, env, check):
        captured.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["approval-operator", "approval-inbox-list"]) == 0
    assert captured[-1][1:4] == ["-m", "okcanvas_agent_runtime", "approval-inbox-list"]
