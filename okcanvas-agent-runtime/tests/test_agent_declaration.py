import json
from pathlib import Path

from okcanvas_agent_runtime.agent.sdk.coding_agent import CODING_AGENT_INSTRUCTIONS
from okcanvas_agent_runtime.core.contracts import CodingAgentResult


def test_declarative_agent_contract_matches_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    instructions = (root / "specs/agents/coding-agent/instructions.md").read_text(encoding="utf-8")
    schema = json.loads(
        (root / "specs/agents/coding-agent/output.schema.json").read_text(encoding="utf-8")
    )
    assert instructions == CODING_AGENT_INSTRUCTIONS
    assert schema == CodingAgentResult.model_json_schema()
