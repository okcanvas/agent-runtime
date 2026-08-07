from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinition, AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog

from .catalog import GroupwareReadCatalog, GroupwareReadContractError


class GroupwareSessionDelegationContractError(RuntimeError):
    code = "GROUPWARE_SESSION_DELEGATION_CONTRACT_INVALID"


@dataclass(frozen=True)
class GroupwareSessionDelegationPolicy:
    schema_version: str
    policy_id: str
    version: str
    root_agent_id: str
    child_agent_id: str
    mcp_server_id: str
    root_output_contract: str
    child_output_contract: str
    root_session_mode: str
    child_session_mode: str
    max_agent_tool_calls_per_turn: int
    max_depth: int
    max_result_bytes: int
    input_mode: str
    output_mode: str
    nested_stream_enabled: bool
    inherit_parent_run_config: bool
    root_session_only: bool
    delegated_identity_required: bool
    route_context_required: bool
    write_enabled: bool
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "root_agent_id": self.root_agent_id,
            "child_agent_id": self.child_agent_id,
            "mcp_server_id": self.mcp_server_id,
            "root_output_contract": self.root_output_contract,
            "child_output_contract": self.child_output_contract,
            "root_session_mode": self.root_session_mode,
            "child_session_mode": self.child_session_mode,
            "max_agent_tool_calls_per_turn": self.max_agent_tool_calls_per_turn,
            "max_depth": self.max_depth,
            "max_result_bytes": self.max_result_bytes,
            "input_mode": self.input_mode,
            "output_mode": self.output_mode,
            "nested_stream_enabled": self.nested_stream_enabled,
            "inherit_parent_run_config": self.inherit_parent_run_config,
            "root_session_only": self.root_session_only,
            "delegated_identity_required": self.delegated_identity_required,
            "route_context_required": self.route_context_required,
            "write_enabled": self.write_enabled,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class GroupwareSessionDelegationBinding:
    policy: GroupwareSessionDelegationPolicy
    parent: AgentDefinition
    child: AgentDefinition
    mcp_server_id: str


class GroupwareSessionDelegationCatalog:
    """Exact Product contract for Session root -> stateless Groupware read Sub-agent.

    This is deliberately separate from the generic STEP049 language-only Agent-as-Tool
    contract.  It permits one narrowly named child with one read-only delegated MCP server,
    different parent/child output contracts, and no child Session persistence.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "groupware" / "session-delegation-policy.json"
        self.policy = self._load()
        self._definitions = AgentDefinitionCatalog(self.project_root)
        self._mcp = MCPServerCatalog(self.project_root)
        self._groupware = GroupwareReadCatalog(self.project_root)

    def resolve(self, parent: AgentDefinition) -> GroupwareSessionDelegationBinding:
        policy = self.policy
        if parent.agent_id != policy.root_agent_id:
            raise GroupwareSessionDelegationContractError(
                "Groupware Session delegation is valid only for the named root Agent"
            )
        child = self._definitions.resolve(policy.child_agent_id)
        if parent.agent_tools != (child.agent_id,):
            raise GroupwareSessionDelegationContractError(
                "Root Agent must declare exactly the Groupware read Sub-agent"
            )
        if parent.session_mode != policy.root_session_mode or parent.output_contract != policy.root_output_contract:
            raise GroupwareSessionDelegationContractError(
                "Root Session or output contract drifted"
            )
        if any((parent.tools, parent.mcp_servers, parent.hosted_tools, parent.handoffs,
                parent.orchestration_children, parent.guardrails)):
            raise GroupwareSessionDelegationContractError(
                "Groupware Session root must not own direct Tools, MCP, Handoffs, orchestration, or Guardrails"
            )
        if parent.workspace_access != "none" or parent.input_mode != "text-only":
            raise GroupwareSessionDelegationContractError(
                "Groupware Session root must remain text-only with no workspace"
            )
        if child.session_mode != policy.child_session_mode or child.output_contract != policy.child_output_contract:
            raise GroupwareSessionDelegationContractError(
                "Groupware child Session or output contract drifted"
            )
        if child.mcp_servers != (policy.mcp_server_id,):
            raise GroupwareSessionDelegationContractError(
                "Groupware child must declare exactly the governed MCP server"
            )
        if any((child.tools, child.hosted_tools, child.handoffs, child.agent_tools,
                child.orchestration_children, child.guardrails, child.skills)):
            raise GroupwareSessionDelegationContractError(
                "Groupware child must be terminal except for its one read-only MCP server"
            )
        if child.workspace_access != "none" or child.input_mode != "text-only":
            raise GroupwareSessionDelegationContractError(
                "Groupware child must remain text-only with no workspace"
            )
        server = self._mcp.resolve(policy.mcp_server_id)
        if (
            server.server_id != self._groupware.policy.server_id
            or not server.is_remote_streamable_http
            or not server.read_only
            or not server.requires_delegated_identity
            or server.allowed_tools != self._groupware.policy.allowed_tools
            or policy.write_enabled
        ):
            raise GroupwareSessionDelegationContractError(
                "Groupware child MCP boundary is not the exact read-only delegated contract"
            )
        if policy.max_agent_tool_calls_per_turn != 1 or policy.max_depth != 1:
            raise GroupwareSessionDelegationContractError(
                "Groupware Session delegation must remain one call at depth one"
            )
        if not all((policy.root_session_only, policy.delegated_identity_required,
                    policy.route_context_required, policy.nested_stream_enabled)):
            raise GroupwareSessionDelegationContractError(
                "Groupware Session safety controls must remain enabled"
            )
        if policy.inherit_parent_run_config:
            raise GroupwareSessionDelegationContractError(
                "Groupware child must use an explicit child RunConfig"
            )
        return GroupwareSessionDelegationBinding(
            policy=policy, parent=parent, child=child, mcp_server_id=server.server_id
        )

    def _load(self) -> GroupwareSessionDelegationPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise GroupwareSessionDelegationContractError(
                "Groupware Session delegation policy is missing or unsafe"
            )
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GroupwareSessionDelegationContractError(
                "Groupware Session delegation policy is not valid UTF-8 JSON"
            ) from exc
        expected = {
            "schema_version", "policy_id", "version", "root_agent_id", "child_agent_id",
            "mcp_server_id", "root_output_contract", "child_output_contract",
            "root_session_mode", "child_session_mode", "max_agent_tool_calls_per_turn",
            "max_depth", "max_result_bytes", "input_mode", "output_mode",
            "nested_stream_enabled", "inherit_parent_run_config", "root_session_only",
            "delegated_identity_required", "route_context_required", "write_enabled",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise GroupwareSessionDelegationContractError(
                "Groupware Session delegation policy keys are not exact"
            )
        exact = {
            "schema_version": "okcanvas-groupware-session-delegation-policy-v1",
            "policy_id": "main-assistant-stateless-groupware-subagent-v1",
            "version": "1.0.0",
            "root_agent_id": "organization-assistant-session-agent",
            "child_agent_id": "groupware-read-agent",
            "mcp_server_id": "groupware-read",
            "root_output_contract": "OrganizationAssistantResult",
            "child_output_contract": "GroupwareReadResult",
            "root_session_mode": "sqlite-v1",
            "child_session_mode": "disabled",
            "max_agent_tool_calls_per_turn": 1,
            "max_depth": 1,
            "max_result_bytes": 8192,
            "input_mode": "MODEL_GENERATED_TEXT",
            "output_mode": "BOUNDED_STRUCTURED_JSON",
            "nested_stream_enabled": True,
            "inherit_parent_run_config": False,
            "root_session_only": True,
            "delegated_identity_required": True,
            "route_context_required": True,
            "write_enabled": False,
        }
        if any(payload[key] != value for key, value in exact.items()):
            raise GroupwareSessionDelegationContractError(
                "Groupware Session delegation policy drifted from the Product boundary"
            )
        return GroupwareSessionDelegationPolicy(
            **payload,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )


def parse_product_routing_context(request: str) -> dict[str, object] | None:
    prefix = "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
    separator = "\n\nUSER REQUEST:\n"
    if not request.startswith(prefix) or separator not in request:
        return None
    encoded, user_request = request[len(prefix):].split(separator, 1)
    if not user_request.strip():
        return None
    try:
        payload = json.loads(encoded)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != "okcanvas-assistant-routing-context-v2":
        return None
    return payload


def requires_groupware_session_delegation(request: str) -> bool:
    payload = parse_product_routing_context(request)
    if payload is None:
        return False
    capabilities = payload.get("required_capabilities")
    groupware = payload.get("groupware_read_policy")
    return bool(
        payload.get("status") == "EXECUTABLE"
        and payload.get("selected_agent_definition_id") == "organization-assistant-session-agent"
        and isinstance(capabilities, list)
        and "groupware-read-v1" in capabilities
        and isinstance(groupware, dict)
        and groupware.get("policy_id") == "groupware-read-v1"
        and groupware.get("write_enabled") is False
        and groupware.get("delegated_identity_required") is True
    )
