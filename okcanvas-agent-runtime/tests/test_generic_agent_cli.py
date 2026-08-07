from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.bootstrap.development_cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_definition_show_cli(capsys) -> None:
    exit_code = main(
        [
            "agent-definition-show",
            "--project-root",
            str(ROOT),
            "--agent-id",
            "coding-agent",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_id"] == "coding-agent"
    assert payload["tools"] == []
    assert payload["handoffs"] == []
    assert len(payload["definition_sha256"]) == 64


def test_generic_run_cli_fails_before_persistence_without_confirmation(tmp_path: Path, capsys) -> None:
    database = tmp_path / "product.sqlite3"
    exit_code = main(
        [
            "generic-agent-run",
            "--project-root",
            str(ROOT),
            "--agent-id",
            "coding-agent",
            "--input",
            "work",
            "--model",
            "test-model",
            "--product-db",
            str(database),
            "--artifact-root",
            str(tmp_path / "artifacts"),
        ]
    )
    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "LIVE_OPT_IN_REQUIRED"
