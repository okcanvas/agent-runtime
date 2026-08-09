from __future__ import annotations

from typing import Any

from .session_delegation import parse_product_routing_context

_ALLOWED_TOOLS = {"search_notices", "search_mail", "list_calendar_events"}


def groupware_operation_hint(request: str) -> dict[str, Any]:
    context = parse_product_routing_context(request)
    if not isinstance(context, dict):
        return {}
    value = context.get("groupware_operation_hint")
    if not isinstance(value, dict):
        return {}
    expected = {"schema_version", "resource_kind", "tool_name", "routing_only"}
    if set(value) != expected or value.get("schema_version") != "okcanvas-groupware-operation-hint-v1":
        return {}
    if value.get("tool_name") not in _ALLOWED_TOOLS or value.get("routing_only") is not True:
        return {}
    return value


def groupware_context_filter(request: str) -> dict[str, Any]:
    context = parse_product_routing_context(request)
    if not isinstance(context, dict):
        return {}
    value = context.get("groupware_context_filter")
    return value if isinstance(value, dict) else {}


def groupware_named_tool_choice(request: str) -> str | None:
    operation = groupware_operation_hint(request)
    if operation:
        return str(operation["tool_name"])
    hint = groupware_context_filter(request)
    tool_name = hint.get("tool_name")
    return tool_name if isinstance(tool_name, str) and tool_name in _ALLOWED_TOOLS else None
