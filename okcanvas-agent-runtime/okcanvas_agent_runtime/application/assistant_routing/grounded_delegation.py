from __future__ import annotations

_ROOT_AGENT_ID = "organization-assistant-session-agent"
_GROUNDED_STRUCTURED_DELEGATION_SCHEMA = "okcanvas-grounded-structured-delegation-v1"
_ALLOWED_GROUNDED_CAPABILITIES = ("groupware-read-v1", "organization-context-read-v1")


def grounded_structured_delegation_context() -> dict[str, object]:
    """Return the exact Product-owned marker for one governed Root-LLM read delegation."""

    return {
        "schema_version": _GROUNDED_STRUCTURED_DELEGATION_SCHEMA,
        "mode": "LLM_SELECTS_AT_MOST_ONE_READ_CHILD",
        "root_agent_id": _ROOT_AGENT_ID,
        "allowed_capabilities": list(_ALLOWED_GROUNDED_CAPABILITIES),
        "max_child_calls": 1,
        "max_child_requests": 1,
        "stable_ids_from_model_accepted": False,
        "write_enabled": False,
        "compound_multi_child_enabled": False,
        "model_can_answer_without_child": True,
        "runtime_admission_required": True,
        "child_mcp_lazy_connect": True,
        "root_direct_mcp": False,
        "legacy_child_selection_authoritative": False,
    }


def grounded_structured_delegation_requested(context: dict[str, object] | None) -> bool:
    if context is None:
        return False
    marker = context.get("grounded_structured_delegation")
    return isinstance(marker, dict) and marker == grounded_structured_delegation_context()
