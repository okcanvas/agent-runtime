from __future__ import annotations

from typing import Any

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyResult


CODEX_READONLY_AGENT_ID = "codex-readonly-agent"
CODEX_THREAD_CONTEXT_KEY = "codex_thread_id_engineer"

CODEX_READONLY_INSTRUCTIONS = """You are the OKCanvas read-only code analysis coordinator.

You must call the codex_engineer tool before answering. The Codex workspace is read-only.
Never claim that a file, command, test, or behavior was inspected unless the Codex tool output
provides evidence. Return repository-relative file paths only. Do not propose that any file was
modified. Separate confirmed findings from unverified items. Preserve the exact distinction
between source inspection and executed validation.
"""


def build_codex_readonly_agent(
    agent_type: type[Any],
    *,
    model: str,
    tool: Any,
    model_settings: Any,
) -> Any:
    return agent_type(
        name="OKCanvas Codex Read-only Agent",
        instructions=CODEX_READONLY_INSTRUCTIONS,
        model=model,
        tools=[tool],
        handoffs=[],
        output_type=CodexReadOnlyResult,
        model_settings=model_settings,
    )
