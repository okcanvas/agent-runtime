from __future__ import annotations

import re
from typing import Any

from okcanvas_agent_runtime.agent.definitions import AgentDefinition

from okcanvas_agent_runtime.agent.subagents.handoffs.errors import NativeHandoffContractError
from okcanvas_agent_runtime.agent.subagents.handoffs.models import NativeHandoffPolicy

_TOOL_NAME_RE = re.compile(r"[^a-zA-Z0-9_]+")


def validate_native_handoff_definitions(
    *,
    parent: AgentDefinition,
    child: AgentDefinition,
    policy: NativeHandoffPolicy,
) -> None:
    if len(parent.handoffs) != 1 or parent.handoffs[0] != child.agent_id:
        raise NativeHandoffContractError("STEP041 requires exactly one declared Handoff target")
    if parent.agent_tools or parent.tools or parent.mcp_servers:
        raise NativeHandoffContractError(
            "STEP041 does not mix Handoff with Agent-as-Tool, Function Tool, or MCP"
        )
    if parent.session_mode != "disabled" or child.session_mode != "disabled":
        raise NativeHandoffContractError("STEP041 does not enable SDK Sessions")
    if child.handoffs or child.agent_tools or child.tools or child.mcp_servers:
        raise NativeHandoffContractError("STEP041 Handoff child must be language-only and terminal")
    if parent.workspace_access != policy.required_workspace_access:
        raise NativeHandoffContractError("Parent Agent workspace policy does not match Handoff policy")
    if child.workspace_access != policy.required_workspace_access:
        raise NativeHandoffContractError("Child Agent workspace policy does not match Handoff policy")
    if policy.require_same_output_contract and child.output_contract != parent.output_contract:
        raise NativeHandoffContractError("STEP041 parent and child must share one output contract")


def validate_sqlite_session_handoff_definitions(
    *,
    parent: AgentDefinition,
    child: AgentDefinition,
    policy: NativeHandoffPolicy,
) -> None:
    if len(parent.handoffs) != 1 or parent.handoffs[0] != child.agent_id:
        raise NativeHandoffPolicyError("STEP047 requires exactly one declared Handoff child")
    if parent.agent_tools or parent.tools or parent.mcp_servers or parent.guardrails:
        raise NativeHandoffPolicyError("STEP047 root must be Tool-free, MCP-free, Agent-as-Tool-free, and Guardrail-free")
    if parent.session_mode != "sqlite-v1" or child.session_mode != "disabled":
        raise NativeHandoffPolicyError("STEP047 requires a SQLite Session root and Session-disabled child")
    if child.handoffs or child.agent_tools or child.tools or child.mcp_servers or child.guardrails:
        raise NativeHandoffPolicyError("STEP047 Handoff child must be terminal and capability-free")
    if parent.workspace_access != policy.required_workspace_access or child.workspace_access != policy.required_workspace_access:
        raise NativeHandoffPolicyError("STEP047 Handoff graph is workspace-free")
    if policy.require_same_output_contract and parent.output_contract != child.output_contract:
        raise NativeHandoffPolicyError("STEP047 Handoff child must share the root output contract")


def build_sdk_native_handoff(
    *,
    child_sdk_agent: Any,
    child_definition: AgentDefinition,
    policy: NativeHandoffPolicy,
) -> Any:
    try:
        from agents import handoff
        from agents.extensions import handoff_filters
    except (ImportError, ModuleNotFoundError) as exc:
        raise NativeHandoffContractError("Installed OpenAI Agents SDK Handoff API is unavailable") from exc
    if policy.input_filter_mode != "REMOVE_ALL_TOOLS":
        raise NativeHandoffContractError("Unsupported Handoff input filter mode")
    tool_suffix = _TOOL_NAME_RE.sub("_", child_definition.agent_id).strip("_")
    return handoff(
        child_sdk_agent,
        tool_name_override=f"transfer_to_{tool_suffix}",
        tool_description_override=(
            f"Transfer control to the declared {child_definition.name} Agent."
        ),
        input_filter=handoff_filters.remove_all_tools,
        nest_handoff_history=policy.nest_handoff_history,
    )
