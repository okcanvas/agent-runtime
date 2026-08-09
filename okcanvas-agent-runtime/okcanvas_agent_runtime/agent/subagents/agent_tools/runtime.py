from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

from okcanvas_agent_runtime.agent.definitions import AgentDefinition

from okcanvas_agent_runtime.agent.subagents.agent_tools.errors import AgentToolContractError
from okcanvas_agent_runtime.agent.subagents.agent_tools.models import AgentToolPolicy

_TOOL_NAME_RE = re.compile(r"[^a-zA-Z0-9_]+")


def validate_agent_tool_definitions(
    *,
    parent: AgentDefinition,
    child: AgentDefinition,
    policy: AgentToolPolicy,
) -> None:
    if len(parent.agent_tools) != 1 or parent.agent_tools[0] != child.agent_id:
        raise AgentToolContractError("STEP042 requires exactly one declared Agent-as-Tool target")
    if parent.handoffs or parent.tools or parent.mcp_servers:
        raise AgentToolContractError(
            "STEP042 does not mix Agent-as-Tool with Handoff, Function Tool, or MCP"
        )
    if parent.session_mode != "disabled" or child.session_mode != "disabled":
        raise AgentToolContractError("STEP042 does not enable SDK Sessions")
    if child.handoffs or child.agent_tools or child.tools or child.mcp_servers:
        raise AgentToolContractError("STEP042 child must be language-only and terminal")
    if parent.workspace_access != policy.required_workspace_access:
        raise AgentToolContractError("Parent workspace policy does not match Agent-as-Tool policy")
    if child.workspace_access != policy.required_workspace_access:
        raise AgentToolContractError("Child workspace policy does not match Agent-as-Tool policy")
    if policy.require_same_output_contract and child.output_contract != parent.output_contract:
        raise AgentToolContractError("STEP042 parent and child must share one output contract")


def validate_sqlite_session_agent_tool_definitions(
    *,
    parent: AgentDefinition,
    child: AgentDefinition,
    policy: AgentToolPolicy,
) -> None:
    if len(parent.agent_tools) != 1 or parent.agent_tools[0] != child.agent_id:
        raise AgentToolContractError("STEP049 requires exactly one declared Agent-as-Tool target")
    if parent.session_mode != "sqlite-v1":
        raise AgentToolContractError("STEP049 requires a SQLite Session-enabled Root Agent")
    if child.session_mode != "disabled":
        raise AgentToolContractError("STEP049 child Agent must remain Session-disabled")
    if parent.handoffs or parent.tools or parent.mcp_servers or parent.guardrails:
        raise AgentToolContractError(
            "STEP049 does not mix Session Agent-as-Tool with Handoff, Function Tool, MCP, or Guardrail"
        )
    if child.handoffs or child.agent_tools or child.tools or child.mcp_servers or child.guardrails:
        raise AgentToolContractError("STEP049 child must be language-only and terminal")
    if parent.workspace_access != policy.required_workspace_access:
        raise AgentToolContractError("Parent workspace policy does not match Agent-as-Tool policy")
    if child.workspace_access != policy.required_workspace_access:
        raise AgentToolContractError("Child workspace policy does not match Agent-as-Tool policy")
    if policy.require_same_output_contract and child.output_contract != parent.output_contract:
        raise AgentToolContractError("STEP049 parent and child must share one output contract")


def agent_tool_name(child_definition: AgentDefinition) -> str:
    suffix = _TOOL_NAME_RE.sub("_", child_definition.agent_id).strip("_")
    return f"invoke_{suffix}"


async def bounded_structured_child_result(
    *,
    result: Any,
    output_type: type[Any],
    max_result_bytes: int,
) -> str:
    try:
        output = result.final_output_as(output_type, raise_if_incorrect_type=True)
        if hasattr(output, "model_dump"):
            payload = output.model_dump(mode="json")
        elif isinstance(output, dict):
            payload = output
        else:
            raise TypeError("Nested Agent output is not structured")
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception as exc:
        raise AgentToolContractError("Nested Agent output could not be normalized") from exc
    if len(serialized.encode("utf-8")) > max_result_bytes:
        raise AgentToolContractError("Nested Agent structured result exceeds the configured bound")
    return serialized


def build_sdk_agent_tool(
    *,
    child_sdk_agent: Any,
    child_definition: AgentDefinition,
    policy: AgentToolPolicy,
    run_config: Any,
    hooks: Any,
    on_stream: Callable[[Any], Awaitable[None]],
    custom_output_extractor: Callable[[Any], Awaitable[str]],
    parameters: type[Any] | None = None,
    input_builder: Callable[[dict[str, Any]], Any] | None = None,
    tool_description: str | None = None,
) -> Any:
    if policy.inherit_parent_run_config:
        raise AgentToolContractError("STEP042 forbids implicit parent RunConfig inheritance")
    if not policy.nested_stream_enabled:
        raise AgentToolContractError("STEP042 requires nested Agent streaming")
    return child_sdk_agent.as_tool(
        tool_name=agent_tool_name(child_definition),
        tool_description=(
            tool_description
            or (
                f"Invoke the declared {child_definition.name} specialist exactly once and return its "
                "bounded structured result to the parent Agent."
            )
        ),
        custom_output_extractor=custom_output_extractor,
        on_stream=on_stream,
        run_config=run_config,
        max_turns=child_definition.max_turns,
        hooks=hooks,
        session=None,
        failure_error_function=None,
        needs_approval=False,
        parameters=parameters,
        input_builder=input_builder,
        include_input_schema=False,
    )
