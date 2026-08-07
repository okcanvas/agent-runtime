from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.application.organization_context import (
    organization_context_named_tool_choice,
    organization_context_request_hint,
)

ROOT = Path(__file__).resolve().parents[1]


def _request(preferred_operation: str) -> str:
    context = {
        "schema_version": "okcanvas-assistant-routing-context-v2",
        "organization_context_request_hint": {
            "schema_version": "okcanvas-organization-context-request-hint-v1",
            "pattern_id": "position-list-v1",
            "intent": "EMPLOYEE_LIST",
            "target_expression": "과장",
            "entity_type_hints": ["POSITION", "EMPLOYEE"],
            "requested_fields": ["LIST"],
            "preferred_operation": preferred_operation,
        },
    }
    return (
        "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True)
        + "\n\nUSER REQUEST:\n과장들 목록"
    )


def test_request_hint_maps_only_admitted_operations_to_named_tools() -> None:
    assert organization_context_named_tool_choice(_request("RESOLVE")) == (
        "resolve_organization_context"
    )
    assert organization_context_named_tool_choice(_request("SEARCH")) == (
        "search_organization_context"
    )
    assert organization_context_named_tool_choice(_request("GET")) is None


def test_request_hint_is_operation_contract_not_entity_evidence() -> None:
    hint = organization_context_request_hint(_request("SEARCH"))
    assert hint["target_expression"] == "과장"
    assert "entity_id" not in hint
    assert "records" not in hint


def test_gateway_binds_named_tool_choice_only_for_organization_context_hint() -> None:
    source = (ROOT / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(
        encoding="utf-8"
    )
    assert "organization_context_named_tool_choice(request)" in source
    assert 'else None\n                    ) or "required"' in source
    assert "tool_choice=child_tool_choice" in source
    assert 'child_agent_kwargs["reset_tool_choice"] = True' in source


def test_bundled_sdk_supports_named_function_tool_choice() -> None:
    source = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/src/agents/models/openai_responses.py"
    ).read_text(encoding="utf-8")
    assert "_validate_named_function_tool_choice" in source
    assert '"type": "function"' in source
    assert '"name": tool_choice' in source


def test_bundled_sdk_mcp_output_is_text_wrapper_when_structured_content_is_disabled() -> None:
    source = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/util.py"
    ).read_text(encoding="utf-8")
    assert 'ToolOutputTextDict(type="text", text=item.text)' in source
    assert "if len(tool_output_list) == 1:" in source
    assert "tool_output = tool_output_list[0]" in source
