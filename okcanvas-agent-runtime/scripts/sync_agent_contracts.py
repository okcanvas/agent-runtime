from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.agent.sdk.coding_agent import CODING_AGENT_INSTRUCTIONS
from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyResult
from okcanvas_agent_runtime.agent.sdk.codex_write_agent import CODEX_WRITE_INSTRUCTIONS
from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteResult
from okcanvas_agent_runtime.core.contracts import CodingAgentResult


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    instructions = root / "specs" / "agents" / "coding-agent" / "instructions.md"
    schema = root / "specs" / "agents" / "coding-agent" / "output.schema.json"
    instructions.write_text(CODING_AGENT_INSTRUCTIONS, encoding="utf-8")
    schema.write_text(
        json.dumps(CodingAgentResult.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    codex_schema = (
        root / "specs" / "agents" / "codex-readonly-agent" / "output.schema.json"
    )
    codex_schema.write_text(
        json.dumps(CodexReadOnlyResult.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_instructions = root / "specs" / "agents" / "codex-write-agent" / "instructions.md"
    write_schema = root / "specs" / "agents" / "codex-write-agent" / "output.schema.json"
    write_instructions.write_text(CODEX_WRITE_INSTRUCTIONS, encoding="utf-8")
    write_schema.write_text(
        json.dumps(CodexWriteResult.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
