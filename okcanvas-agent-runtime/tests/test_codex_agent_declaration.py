import json
from pathlib import Path

from okcanvas_agent_runtime.agent.sdk.codex_readonly_agent import CODEX_READONLY_INSTRUCTIONS
from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyResult


def test_codex_agent_spec_matches_runtime_instructions() -> None:
    root = Path(__file__).resolve().parents[1]
    instructions = (
        root / "specs" / "agents" / "codex-readonly-agent" / "instructions.md"
    ).read_text(encoding="utf-8")
    assert instructions == CODEX_READONLY_INSTRUCTIONS
    schema = json.loads((root / "specs" / "agents" / "codex-readonly-agent" / "output.schema.json").read_text(encoding="utf-8"))
    assert schema == CodexReadOnlyResult.model_json_schema()
