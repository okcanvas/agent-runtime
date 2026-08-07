from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.bootstrap.development_cli import main


def test_reference_list_cli(capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    assert main(["reference-list", "--project-root", str(root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["references"]) == 4
    assert payload["references"][0]["reference_id"] == "openai-agents-python"


def test_reference_read_cli_rejects_traversal(capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    assert (
        main(
            [
                "reference-read",
                "--project-root",
                str(root),
                "--reference-id",
                "openai-agents-python",
                "--path",
                "../AGENTS.md",
                "--start-line",
                "1",
                "--end-line",
                "1",
            ]
        )
        == 2
    )
    payload = json.loads(capsys.readouterr().err)
    assert payload["code"] == "REFERENCE_PATH_ERROR"
