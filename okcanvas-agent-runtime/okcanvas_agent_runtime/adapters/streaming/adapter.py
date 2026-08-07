from __future__ import annotations

from typing import Any


def adapt_sdk_stream_event(event: Any) -> tuple[str, dict[str, object]] | None:
    """Convert official SDK stream events to a bounded safe ephemeral envelope.

    Raw Tool arguments/results and reasoning content are intentionally not forwarded.
    """

    kind = str(getattr(event, "type", ""))
    if kind == "raw_response_event":
        data = getattr(event, "data", None)
        data_type = str(getattr(data, "type", ""))
        if data_type != "response.output_text.delta":
            return None
        delta = getattr(data, "delta", None)
        if not isinstance(delta, str) or not delta:
            return None
        return (
            "model.text.delta",
            {
                "delta": delta,
                "response_event_type": data_type,
                "persisted": False,
            },
        )
    if kind == "run_item_stream_event":
        item = getattr(event, "item", None)
        item_type = str(getattr(item, "type", "unknown"))
        agent = getattr(item, "agent", None)
        return (
            "run.item",
            {
                "name": str(getattr(event, "name", "unknown")),
                "item_type": item_type,
                "agent_name": str(getattr(agent, "name", "")) or None,
                "content_persisted": False,
                "tool_arguments_persisted": False,
                "tool_result_persisted": False,
            },
        )
    if kind == "agent_updated_stream_event":
        agent = getattr(event, "new_agent", None)
        return (
            "agent.updated",
            {
                "agent_name": str(getattr(agent, "name", "unknown")),
                "instructions_persisted": False,
            },
        )
    return None
