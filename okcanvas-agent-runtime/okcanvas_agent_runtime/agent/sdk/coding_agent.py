from __future__ import annotations

from okcanvas_agent_runtime.core.contracts import CodingAgentResult

AGENT_ID = "coding-agent"
AGENT_NAME = "OKCanvas Coding Analyst"

CODING_AGENT_INSTRUCTIONS = """Inspect only the information actually provided in the request.
Do not claim to have read files, executed commands, called tools, or validated a build unless the run
contains evidence of that action. This STEP has no tools and no workspace access.
Distinguish confirmed findings from inferences. Put every unresolved point in `unverified`.
Return only the configured structured output contract.
"""


def build_agent(sdk_agent_type: type, *, model: str):
    """Build the STEP001 tool-free Agent using the supplied SDK Agent type."""
    return sdk_agent_type(
        name=AGENT_NAME,
        instructions=CODING_AGENT_INSTRUCTIONS,
        model=model,
        tools=[],
        handoffs=[],
        output_type=CodingAgentResult,
    )
