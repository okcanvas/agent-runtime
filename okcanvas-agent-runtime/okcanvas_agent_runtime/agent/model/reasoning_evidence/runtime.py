from __future__ import annotations

from okcanvas_agent_runtime.agent.model.reasoning_evidence.models import ReasoningEvidencePolicy


def build_sdk_reasoning_model_settings_kwargs(policy: ReasoningEvidencePolicy) -> dict[str, object]:
    """Return explicit SDK ModelSettings values that request no reasoning summary or extras."""

    if policy.reasoning_summary_requested or policy.response_include:
        raise ValueError("Reasoning summary or response includes are outside the minimization policy")
    return {"reasoning": None, "response_include": []}


def count_reasoning_items(response: object) -> int:
    """Count reasoning items without copying IDs, summaries, content, or provider data."""

    output = getattr(response, "output", ()) or ()
    count = 0
    for item in output:
        item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
        if item_type == "reasoning":
            count += 1
    return count
