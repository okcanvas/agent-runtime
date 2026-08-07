from __future__ import annotations

from okcanvas_agent_runtime.adapters.mcp.clients.openai_factory import RemoteMCPResultLimitError
from okcanvas_agent_runtime.adapters.openai.generic_gateway import _safe_mcp_failure_diagnostic
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionErrorCode


def test_remote_mcp_result_limit_error_exposes_only_bounded_diagnostics() -> None:
    error = RemoteMCPResultLimitError(
        server_id="organization-context-read", observed_chars=34994, max_result_chars=32000
    )
    wrapper = RuntimeError("sdk wrapper")
    wrapper.__cause__ = error
    diagnostic, retryable, detail_type = _safe_mcp_failure_diagnostic(
        wrapper, {"server_id": "organization-context-read", "tool_name": "resolve_organization_context"}
    )
    assert retryable is False
    assert detail_type == "RemoteMCPResultLimitError"
    assert diagnostic == {
        "failure_stage": "mcp_tool_call",
        "failure_category": "MCP_RESULT_LIMIT_EXCEEDED",
        "server_id": "organization-context-read",
        "tool_name": "resolve_organization_context",
        "observed_chars": 34994,
        "max_result_chars": 32000,
        "tool_arguments_persisted": False,
        "tool_result_persisted": False,
        "raw_error_persisted": False,
    }


def test_generic_execution_failure_retains_safe_diagnostic_without_raw_payload() -> None:
    diagnostic = {
        "failure_stage": "mcp_tool_call",
        "failure_category": "MCP_RESULT_LIMIT_EXCEEDED",
        "server_id": "organization-context-read",
        "tool_name": "resolve_organization_context",
        "observed_chars": 34994,
        "max_result_chars": 32000,
        "tool_arguments_persisted": False,
        "tool_result_persisted": False,
        "raw_error_persisted": False,
    }
    failure = GenericExecutionFailure(
        GenericExecutionErrorCode.SDK_RUN_FAILED,
        "OpenAI Agents SDK run failed",
        retryable=False,
        detail_type="RemoteMCPResultLimitError",
        diagnostic=diagnostic,
    )
    assert failure.diagnostic == diagnostic
    assert "Authorization" not in repr(failure.diagnostic)
    assert "query" not in repr(failure.diagnostic)


def test_structured_output_validation_diagnostic_exposes_only_field_paths_and_types() -> None:
    from pydantic import BaseModel, Field, ValidationError
    from okcanvas_agent_runtime.adapters.openai.generic_gateway import (
        _safe_structured_output_failure_diagnostic,
    )

    class Contract(BaseModel):
        required_value: str = Field(min_length=1)

    try:
        Contract.model_validate({"required_value": ""})
    except ValidationError as validation:
        wrapper = RuntimeError("sdk wrapper")
        wrapper.__cause__ = validation
        diagnostic = _safe_structured_output_failure_diagnostic(
            wrapper,
            output_contract="OrganizationContextReadResult",
            agent_id="organization-context-read-agent",
        )
    else:
        raise AssertionError("validation failure expected")

    assert diagnostic["failure_stage"] == "child_structured_output"
    assert diagnostic["failure_category"] == "PYDANTIC_OUTPUT_VALIDATION_FAILED"
    assert diagnostic["output_contract"] == "OrganizationContextReadResult"
    assert diagnostic["agent_id"] == "organization-context-read-agent"
    assert diagnostic["validation_error_count"] == 1
    assert diagnostic["validation_errors"] == [
        {"location": ["required_value"], "type": "string_too_short"}
    ]
    serialized = repr(diagnostic)
    assert "sdk wrapper" not in serialized
    assert "required_value': ''" not in serialized
    assert diagnostic["model_output_persisted"] is False
    assert diagnostic["tool_arguments_persisted"] is False
    assert diagnostic["tool_result_persisted"] is False
    assert diagnostic["raw_error_persisted"] is False


def test_model_behavior_diagnostic_is_bounded_without_raw_output() -> None:
    from okcanvas_agent_runtime.adapters.openai.generic_gateway import (
        _safe_structured_output_failure_diagnostic,
    )

    ModelBehaviorError = type("ModelBehaviorError", (RuntimeError,), {})
    diagnostic = _safe_structured_output_failure_diagnostic(
        ModelBehaviorError("sensitive raw model output"),
        output_contract="OrganizationContextReadResult",
        agent_id="organization-context-read-agent",
    )
    assert diagnostic["failure_category"] == "SDK_MODEL_BEHAVIOR_ERROR"
    assert diagnostic["validation_errors"] == []
    assert "sensitive raw model output" not in repr(diagnostic)
    assert diagnostic["raw_error_persisted"] is False
