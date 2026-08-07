from __future__ import annotations

import json
from typing import Any

from okcanvas_agent_runtime.agent.guardrails.errors import GuardrailDefinitionContractError
from okcanvas_agent_runtime.agent.guardrails.models import GuardrailKind, GuardrailRuntime


def _input_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def build_sdk_agent_guardrails(runtimes: tuple[GuardrailRuntime, ...]) -> tuple[list[Any], list[Any]]:
    try:
        from agents import GuardrailFunctionOutput
        from agents.decorators import input_guardrail, output_guardrail
    except (ImportError, ModuleNotFoundError) as exc:
        raise GuardrailDefinitionContractError("OpenAI Agents Guardrail SDK is unavailable") from exc
    input_items: list[Any] = []
    output_items: list[Any] = []
    for runtime in runtimes:
        if runtime.kind is GuardrailKind.INPUT:
            async def input_check(context, agent, input, _runtime=runtime):  # type: ignore[no-untyped-def]
                triggered = bool(_runtime.marker and _runtime.marker in _input_text(input))
                return GuardrailFunctionOutput(
                    output_info={"guardrail_id": _runtime.guardrail_id, "matched": triggered},
                    tripwire_triggered=triggered,
                )
            input_check.__name__ = runtime.guardrail_id.replace("-", "_")
            input_items.append(input_guardrail(name=runtime.guardrail_id, run_in_parallel=runtime.run_in_parallel)(input_check))
        elif runtime.kind is GuardrailKind.OUTPUT:
            async def output_check(context, agent, output, _runtime=runtime):  # type: ignore[no-untyped-def]
                if hasattr(output, "model_dump"):
                    raw = json.dumps(output.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
                else:
                    raw = str(output)
                triggered = bool(_runtime.marker and _runtime.marker in raw)
                return GuardrailFunctionOutput(
                    output_info={"guardrail_id": _runtime.guardrail_id, "matched": triggered},
                    tripwire_triggered=triggered,
                )
            output_check.__name__ = runtime.guardrail_id.replace("-", "_")
            output_items.append(output_guardrail(name=runtime.guardrail_id)(output_check))
    return input_items, output_items


def attach_sdk_tool_guardrails(tool: Any, runtimes: tuple[GuardrailRuntime, ...]) -> None:
    try:
        from agents import ToolGuardrailFunctionOutput
        from agents.decorators import tool_input_guardrail, tool_output_guardrail
    except (ImportError, ModuleNotFoundError) as exc:
        raise GuardrailDefinitionContractError("OpenAI Agents Tool Guardrail SDK is unavailable") from exc
    input_items: list[Any] = []
    output_items: list[Any] = []
    for runtime in runtimes:
        if runtime.kind is GuardrailKind.TOOL_INPUT:
            def tool_input_check(data, _runtime=runtime):  # type: ignore[no-untyped-def]
                return ToolGuardrailFunctionOutput.raise_exception(
                    output_info={"guardrail_id": _runtime.guardrail_id, "reason_code": "POLICY_DENY"}
                )
            tool_input_check.__name__ = runtime.guardrail_id.replace("-", "_")
            input_items.append(tool_input_guardrail(name=runtime.guardrail_id)(tool_input_check))
        elif runtime.kind is GuardrailKind.TOOL_OUTPUT:
            def tool_output_check(data, _runtime=runtime):  # type: ignore[no-untyped-def]
                return ToolGuardrailFunctionOutput.raise_exception(
                    output_info={"guardrail_id": _runtime.guardrail_id, "reason_code": "POLICY_DENY"}
                )
            tool_output_check.__name__ = runtime.guardrail_id.replace("-", "_")
            output_items.append(tool_output_guardrail(name=runtime.guardrail_id)(tool_output_check))
    tool.tool_input_guardrails = input_items
    tool.tool_output_guardrails = output_items
