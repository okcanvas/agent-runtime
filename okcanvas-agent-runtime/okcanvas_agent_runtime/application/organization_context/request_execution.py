from __future__ import annotations

import json
from typing import Any

_ROUTING_PREFIX = "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
_ROUTING_SEPARATOR = "\n\nUSER REQUEST:\n"
_ALLOWED_PREFERRED_OPERATIONS = {
    "RESOLVE": "resolve_organization_context",
    "SEARCH": "search_organization_context",
    "GET": "get_organization_entity",
}


def organization_context_request_hint(request: str) -> dict[str, Any]:
    """Return the immutable Organization Context request hint, if present.

    The hint selects an execution operation only. It is not Entity evidence and
    must never be used to fabricate an Entity identity or result.
    """

    if not request.startswith(_ROUTING_PREFIX) or _ROUTING_SEPARATOR not in request:
        return {}
    context_text = request[len(_ROUTING_PREFIX) :].split(_ROUTING_SEPARATOR, 1)[0]
    try:
        context = json.loads(context_text)
    except json.JSONDecodeError:
        return {}
    hint = context.get("organization_context_request_hint") if isinstance(context, dict) else None
    return hint if isinstance(hint, dict) else {}


def organization_context_named_tool_choice(request: str) -> str | None:
    """Resolve a product-owned named Tool choice from an admitted short request.

    Only the operations emitted by the immutable short-expression or Session-context
    routing contracts are accepted. Unknown or missing values fail closed to the existing
    required-tool policy rather than guessing a Tool.
    """

    hint = organization_context_request_hint(request)
    preferred_operation = hint.get("preferred_operation")
    if not isinstance(preferred_operation, str):
        return None
    return _ALLOWED_PREFERRED_OPERATIONS.get(preferred_operation)
