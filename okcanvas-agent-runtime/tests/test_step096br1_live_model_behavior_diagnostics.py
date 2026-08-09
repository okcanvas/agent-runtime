from __future__ import annotations

from types import SimpleNamespace

from okcanvas_agent_runtime.adapters.openai.generic_gateway import (
    _safe_model_behavior_failure_diagnostic,
    _safe_model_output_shape,
)


class ModelBehaviorError(Exception):
    pass


def _error(message: str) -> Exception:
    return ModelBehaviorError(message)


def test_step096br1_model_output_shape_is_content_free() -> None:
    response = SimpleNamespace(
        output=[
            SimpleNamespace(type="message", content="secret-message"),
            SimpleNamespace(type="function_call", name="secret-tool", arguments="secret-args"),
            SimpleNamespace(type="reasoning", summary="secret-reasoning"),
            SimpleNamespace(type="future_provider_item", payload="secret-other"),
        ]
    )
    assert _safe_model_output_shape(response) == {
        "message": 1,
        "function_call": 1,
        "reasoning": 1,
        "other": 1,
    }


def test_step096br1_model_behavior_categories_are_safe_and_payload_free() -> None:
    cases = {
        "Invalid JSON input for tool invoke_secret: {not-json}": "TOOL_ARGUMENT_JSON_INVALID",
        "Invalid JSON input for tool invoke_secret: 1 validation error for SecretModel": "TOOL_ARGUMENT_SCHEMA_INVALID",
        "Failed to serialize structured tool input for invoke_secret: sensitive": "TOOL_ARGUMENT_SERIALIZATION_FAILED",
        "Agent tool called with invalid input": "TOOL_INPUT_BUILDER_INVALID",
        "Tool secret_tool not found in agent Secret Agent": "UNKNOWN_TOOL_CALL",
        "Invalid JSON when parsing {secret} for SecretAdapter; sensitive": "STRUCTURED_FINAL_OUTPUT_INVALID",
        "Model returned no final output for the structured output type.": "STRUCTURED_FINAL_OUTPUT_MISSING",
        "Model did not produce a final response!": "MODEL_FINAL_RESPONSE_MISSING",
        "unexpected sensitive model behavior": "MODEL_BEHAVIOR_OTHER",
    }
    for message, expected in cases.items():
        diagnostic = _safe_model_behavior_failure_diagnostic(_error(message))
        assert diagnostic == {
            "detail_type": "ModelBehaviorError",
            "model_behavior_category": expected,
            "raw_model_output_persisted": False,
            "raw_tool_arguments_persisted": False,
            "raw_error_message_persisted": False,
        }
        rendered = repr(diagnostic)
        assert "secret" not in rendered.lower()
        assert "sensitive" not in rendered.lower()


def test_step096br1_non_model_behavior_error_has_no_model_diagnostic() -> None:
    assert _safe_model_behavior_failure_diagnostic(RuntimeError("sensitive")) is None
