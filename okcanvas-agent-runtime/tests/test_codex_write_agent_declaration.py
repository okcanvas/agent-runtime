import json
from pathlib import Path

from okcanvas_agent_runtime.agent.sdk.codex_write_agent import CODEX_WRITE_INSTRUCTIONS
from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteResult


def test_codex_write_agent_spec_matches_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = root / "specs" / "agents" / "codex-write-agent"
    assert (spec / "instructions.md").read_text(encoding="utf-8") == CODEX_WRITE_INSTRUCTIONS
    assert json.loads((spec / "output.schema.json").read_text(encoding="utf-8")) == CodexWriteResult.model_json_schema()
