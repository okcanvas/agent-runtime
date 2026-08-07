from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinition, AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.application.groupware_read.session_delegation import parse_product_routing_context

from .remote_catalog import OrganizationContextReadCatalog


class OrganizationContextSessionDelegationContractError(RuntimeError):
    code = "ORGANIZATION_CONTEXT_SESSION_DELEGATION_CONTRACT_INVALID"


@dataclass(frozen=True)
class OrganizationContextSessionDelegationPolicy:
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
    production_sot: str
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
            "production_sot": self.production_sot,
            "write_enabled": self.write_enabled,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class OrganizationContextSessionDelegationBinding:
    policy: OrganizationContextSessionDelegationPolicy
    parent: AgentDefinition
    child: AgentDefinition
    mcp_server_id: str


class OrganizationContextSessionDelegationCatalog:
    """Exact Session root -> stateless Organization Context read child contract."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "organization-context" / "session-delegation-policy.json"
        self.policy = self._load()
        self._definitions = AgentDefinitionCatalog(self.project_root)
        self._mcp = MCPServerCatalog(self.project_root)
        self._context = OrganizationContextReadCatalog(self.project_root)

    def resolve(self, parent: AgentDefinition) -> OrganizationContextSessionDelegationBinding:
        policy = self.policy
        if parent.agent_id != policy.root_agent_id:
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context Session delegation is valid only for the named root Agent"
            )
        child = self._definitions.resolve(policy.child_agent_id)
        if parent.agent_tools != (child.agent_id,):
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context root must declare exactly the read child"
            )
        if parent.session_mode != policy.root_session_mode or parent.output_contract != policy.root_output_contract:
            raise OrganizationContextSessionDelegationContractError("Organization Context root contract drifted")
        if any((parent.tools, parent.mcp_servers, parent.hosted_tools, parent.handoffs,
                parent.orchestration_children, parent.guardrails, parent.skills)):
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context root must not own direct execution capabilities"
            )
        if parent.workspace_access != "none" or parent.input_mode != "text-only":
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context root must remain text-only and workspace-free"
            )
        if child.session_mode != policy.child_session_mode or child.output_contract != policy.child_output_contract:
            raise OrganizationContextSessionDelegationContractError("Organization Context child contract drifted")
        if child.mcp_servers != (policy.mcp_server_id,):
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context child must declare exactly the governed MCP server"
            )
        if any((child.tools, child.hosted_tools, child.handoffs, child.agent_tools,
                child.orchestration_children, child.guardrails, child.skills)):
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context child must be terminal except for its read-only MCP server"
            )
        if child.workspace_access != "none" or child.input_mode != "text-only":
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context child must remain text-only and workspace-free"
            )
        server = self._mcp.resolve(policy.mcp_server_id)
        if (
            server.server_id != self._context.policy.server_id
            or not server.is_remote_streamable_http
            or not server.read_only
            or not server.requires_delegated_identity
            or server.allowed_tools != self._context.policy.allowed_tools
            or policy.production_sot != "DATABASE"
            or policy.write_enabled
        ):
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context child MCP boundary is not the exact database-SOT read contract"
            )
        if policy.max_agent_tool_calls_per_turn != 1 or policy.max_depth != 1:
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context Session delegation must remain one call at depth one"
            )
        if not all((policy.root_session_only, policy.delegated_identity_required,
                    policy.route_context_required, policy.nested_stream_enabled)):
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context Session safety controls must remain enabled"
            )
        if policy.inherit_parent_run_config:
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context child must use an explicit child RunConfig"
            )
        return OrganizationContextSessionDelegationBinding(
            policy=policy, parent=parent, child=child, mcp_server_id=server.server_id
        )

    def _load(self) -> OrganizationContextSessionDelegationPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context Session delegation policy is missing or unsafe"
            )
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context Session delegation policy is invalid UTF-8 JSON"
            ) from exc
        expected = {
            "schema_version", "policy_id", "version", "root_agent_id", "child_agent_id",
            "mcp_server_id", "root_output_contract", "child_output_contract", "root_session_mode",
            "child_session_mode", "max_agent_tool_calls_per_turn", "max_depth", "max_result_bytes",
            "input_mode", "output_mode", "nested_stream_enabled", "inherit_parent_run_config",
            "root_session_only", "delegated_identity_required", "route_context_required",
            "production_sot", "write_enabled",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context Session delegation policy keys are not exact"
            )
        exact = {
            "schema_version": "okcanvas-organization-context-session-delegation-policy-v1",
            "policy_id": "organization-context-session-stateless-read-subagent-v1",
            "version": "1.0.0",
            "root_agent_id": "organization-context-session-agent",
            "child_agent_id": "organization-context-read-agent",
            "mcp_server_id": "organization-context-read",
            "root_output_contract": "OrganizationAssistantResult",
            "child_output_contract": "OrganizationContextReadResult",
            "root_session_mode": "sqlite-v1",
            "child_session_mode": "disabled",
            "max_agent_tool_calls_per_turn": 1,
            "max_depth": 1,
            "max_result_bytes": 16384,
            "input_mode": "MODEL_GENERATED_TEXT",
            "output_mode": "BOUNDED_STRUCTURED_JSON",
            "nested_stream_enabled": True,
            "inherit_parent_run_config": False,
            "root_session_only": True,
            "delegated_identity_required": True,
            "route_context_required": True,
            "production_sot": "DATABASE",
            "write_enabled": False,
        }
        if any(payload[key] != value for key, value in exact.items()):
            raise OrganizationContextSessionDelegationContractError(
                "Organization Context Session delegation policy drifted"
            )
        return OrganizationContextSessionDelegationPolicy(
            **payload,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )


def requires_organization_context_session_delegation(request: str) -> bool:
    payload = parse_product_routing_context(request)
    if payload is None:
        return False
    capabilities = payload.get("required_capabilities")
    policy = payload.get("organization_context_read_policy")
    return bool(
        payload.get("status") == "EXECUTABLE"
        and payload.get("selected_agent_definition_id") == "organization-context-session-agent"
        and isinstance(capabilities, list)
        and "organization-context-read-v1" in capabilities
        and isinstance(policy, dict)
        and policy.get("policy_id") == "organization-context-read-v1"
        and policy.get("production_sot") == "DATABASE"
        and policy.get("write_enabled") is False
        and policy.get("delegated_identity_required") is True
    )
