from __future__ import annotations

import json

_ROUTING_PREFIX = "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
_ROUTING_SEPARATOR = "\n\nUSER REQUEST:\n"


def extract_grounded_routing_context(request: str) -> dict[str, object] | None:
    """Return the Product-owned routing context only for a valid Session Root envelope."""

    if not request.startswith(_ROUTING_PREFIX) or _ROUTING_SEPARATOR not in request:
        return None
    encoded, _utterance = request[len(_ROUTING_PREFIX) :].split(_ROUTING_SEPARATOR, 1)
    try:
        context = json.loads(encoded)
    except json.JSONDecodeError:
        return None
    if not isinstance(context, dict):
        return None
    if context.get("schema_version") != "okcanvas-assistant-routing-context-v2":
        return None
    if context.get("selected_agent_definition_id") != "organization-assistant-session-agent":
        return None
    return context


def extract_grounded_session_utterance(request: str) -> str | None:
    """Extract the untouched user turn only from the Product-owned assistant envelope.

    Direct generic Agent runs are intentionally excluded. Grounded enrichment is a Session Assistant
    feature and must not become an implicit routing bypass for arbitrary Agent execution.
    """

    context = extract_grounded_routing_context(request)
    if context is None:
        return None
    _encoded, utterance = request[len(_ROUTING_PREFIX) :].split(_ROUTING_SEPARATOR, 1)
    return utterance if utterance.strip() else None
