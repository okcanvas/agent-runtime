from __future__ import annotations

from typing import Any

from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteResult


CODEX_WRITE_AGENT_ID = "codex-write-agent"
CODEX_WRITE_THREAD_CONTEXT_KEY = "codex_thread_id_writer"

CODEX_WRITE_INSTRUCTIONS = """You are the OKCanvas controlled code-change coordinator.

You must call the codex_engineer tool before answering. The Codex workspace is a disposable
Git copy and write access has already been explicitly approved for this single run. Inspect the
actual implementation and tests, then make the smallest source-code change that fixes the stated
defect. Never modify tests, project instructions, dependency files, or unrelated files. Do not
install packages, use the network, commit, stage, or create new files. Prefer apply_patch. The
independent validator runs after your work; do not claim validation success unless Codex actually
ran it. Return only repository-relative paths and report exactly which files were modified.
"""


def build_codex_write_agent(
    agent_type: type[Any],
    *,
    model: str,
    tool: Any,
    model_settings: Any,
) -> Any:
    return agent_type(
        name="OKCanvas Codex Controlled Write Agent",
        instructions=CODEX_WRITE_INSTRUCTIONS,
        model=model,
        tools=[tool],
        handoffs=[],
        output_type=CodexWriteResult,
        model_settings=model_settings,
    )
