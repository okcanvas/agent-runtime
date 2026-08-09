from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinition, AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.application.groupware_read import GroupwareReadCatalog, parse_product_routing_context
from okcanvas_agent_runtime.application.organization_context import OrganizationContextReadCatalog


class CrossDomainSessionContractError(RuntimeError):
    code = "CROSS_DOMAIN_SESSION_CONTRACT_INVALID"


@dataclass(frozen=True)
class CrossDomainSessionTargetPolicy:
    policy_id: str
    domain: str
    child_agent_id: str
    mcp_server_id: str
    child_output_contract: str
    max_result_bytes: int
    input_mode: str
    output_mode: str
    nested_stream_enabled: bool
    inherit_parent_run_config: bool


@dataclass(frozen=True)
class CrossDomainSessionDelegationPolicy:
    schema_version: str
    policy_id: str
    version: str
    root_agent_id: str
    root_output_contract: str
    root_session_mode: str
    max_agent_tool_calls_per_turn: int
    max_depth: int
    delegated_identity_required: bool
    route_context_required: bool
    write_enabled: bool
    targets: tuple[CrossDomainSessionTargetPolicy, ...]
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "root_agent_id": self.root_agent_id,
            "root_output_contract": self.root_output_contract,
            "root_session_mode": self.root_session_mode,
            "max_agent_tool_calls_per_turn": self.max_agent_tool_calls_per_turn,
            "max_depth": self.max_depth,
            "delegated_identity_required": self.delegated_identity_required,
            "route_context_required": self.route_context_required,
            "write_enabled": self.write_enabled,
            "targets": [
                {
                    "policy_id": item.policy_id,
                    "domain": item.domain,
                    "child_agent_id": item.child_agent_id,
                    "mcp_server_id": item.mcp_server_id,
                    "child_output_contract": item.child_output_contract,
                    "max_result_bytes": item.max_result_bytes,
                    "input_mode": item.input_mode,
                    "output_mode": item.output_mode,
                    "nested_stream_enabled": item.nested_stream_enabled,
                    "inherit_parent_run_config": item.inherit_parent_run_config,
                }
                for item in self.targets
            ],
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class CrossDomainSessionTargetBinding:
    domain: str
    policy: CrossDomainSessionTargetPolicy
    child: AgentDefinition
    mcp_server_id: str


@dataclass(frozen=True)
class CrossDomainSessionDelegationBinding:
    policy: CrossDomainSessionDelegationPolicy
    parent: AgentDefinition
    targets: tuple[CrossDomainSessionTargetBinding, ...]

    def target_for_request(self, request: str) -> CrossDomainSessionTargetBinding | None:
        payload = parse_product_routing_context(request)
        if payload is None:
            return None
        if payload.get("status") != "EXECUTABLE":
            return None
        if payload.get("selected_agent_definition_id") != self.parent.agent_id:
            raise CrossDomainSessionContractError("Routing context selected a different Session root")
        capabilities = payload.get("required_capabilities")
        if not isinstance(capabilities, list):
            raise CrossDomainSessionContractError("Routing context capabilities are missing")
        requested_domains: list[str] = []
        if "groupware-read-v1" in capabilities:
            requested_domains.append("GROUPWARE")
        if "organization-context-read-v1" in capabilities:
            requested_domains.append("ORGANIZATION_CONTEXT")
        if not requested_domains:
            return None
        if len(requested_domains) != 1:
            raise CrossDomainSessionContractError("Exactly one delegated read domain is required per Turn")
        for target in self.targets:
            if target.domain == requested_domains[0]:
                return target
        raise CrossDomainSessionContractError("Requested delegated read domain is not declared")


class CrossDomainSessionDelegationCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "assistant" / "cross-domain-session-delegation-policy.json"
        self._definitions = AgentDefinitionCatalog(self.project_root)
        self._mcp = MCPServerCatalog(self.project_root)
        self._groupware = GroupwareReadCatalog(self.project_root)
        self._organization = OrganizationContextReadCatalog(self.project_root)

    def resolve(self, parent: AgentDefinition) -> CrossDomainSessionDelegationBinding:
        policy = self._load()
        if parent.agent_id != policy.root_agent_id:
            raise CrossDomainSessionContractError("Cross-domain Session root Agent ID drifted")
        if parent.session_mode != policy.root_session_mode or parent.output_contract != policy.root_output_contract:
            raise CrossDomainSessionContractError("Cross-domain Session root contract drifted")
        expected_children = tuple(item.child_agent_id for item in policy.targets)
        if parent.agent_tools != expected_children:
            raise CrossDomainSessionContractError("Cross-domain Session root child graph drifted")
        if any((parent.tools, parent.mcp_servers, parent.hosted_tools, parent.handoffs,
                parent.orchestration_children, parent.guardrails, parent.skills)):
            raise CrossDomainSessionContractError("Cross-domain Session root must own only declared stateless child Agents")
        if parent.workspace_access != "none" or parent.input_mode != "text-only":
            raise CrossDomainSessionContractError("Cross-domain Session root must remain text-only with no workspace")
        bindings: list[CrossDomainSessionTargetBinding] = []
        for item in policy.targets:
            child = self._definitions.resolve(item.child_agent_id)
            if child.session_mode != "disabled" or child.output_contract != item.child_output_contract:
                raise CrossDomainSessionContractError("Cross-domain child Session/output contract drifted")
            if child.mcp_servers != (item.mcp_server_id,):
                raise CrossDomainSessionContractError("Cross-domain child must declare exactly its governed MCP server")
            if any((child.tools, child.hosted_tools, child.handoffs, child.agent_tools,
                    child.orchestration_children, child.guardrails, child.skills)):
                raise CrossDomainSessionContractError("Cross-domain child must remain terminal except for one read-only MCP server")
            server = self._mcp.resolve(item.mcp_server_id)
            if not server.is_remote_streamable_http or not server.read_only or not server.requires_delegated_identity:
                raise CrossDomainSessionContractError("Cross-domain child MCP must remain delegated read-only HTTPS")
            if item.domain == "GROUPWARE":
                if item.child_agent_id != self._groupware.policy.agent_id or item.mcp_server_id != self._groupware.policy.server_id:
                    raise CrossDomainSessionContractError("Groupware cross-domain target drifted from Groupware read policy")
                if server.allowed_tools != self._groupware.policy.allowed_tools:
                    raise CrossDomainSessionContractError("Groupware cross-domain Tool allowlist drifted")
            elif item.domain == "ORGANIZATION_CONTEXT":
                if item.child_agent_id != self._organization.policy.agent_id or item.mcp_server_id != self._organization.policy.server_id:
                    raise CrossDomainSessionContractError("Organization Context cross-domain target drifted from read policy")
                if server.allowed_tools != self._organization.policy.allowed_tools:
                    raise CrossDomainSessionContractError("Organization Context cross-domain Tool allowlist drifted")
                if self._organization.policy.production_sot != "DATABASE":
                    raise CrossDomainSessionContractError("Organization Context production SOT drifted")
            else:
                raise CrossDomainSessionContractError("Unsupported cross-domain target")
            bindings.append(CrossDomainSessionTargetBinding(item.domain, item, child, server.server_id))
        if policy.max_agent_tool_calls_per_turn != 1 or policy.max_depth != 1:
            raise CrossDomainSessionContractError("Cross-domain Session delegation must remain one child call at depth one")
        if not policy.delegated_identity_required or not policy.route_context_required or policy.write_enabled:
            raise CrossDomainSessionContractError("Cross-domain Session safety controls drifted")
        return CrossDomainSessionDelegationBinding(policy=policy, parent=parent, targets=tuple(bindings))

    def _load(self) -> CrossDomainSessionDelegationPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise CrossDomainSessionContractError("Cross-domain Session policy is missing or unsafe")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CrossDomainSessionContractError("Cross-domain Session policy is invalid UTF-8 JSON") from exc
        expected = {
            "schema_version", "policy_id", "version", "root_agent_id", "root_output_contract",
            "root_session_mode", "max_agent_tool_calls_per_turn", "max_depth",
            "delegated_identity_required", "route_context_required", "write_enabled", "targets",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise CrossDomainSessionContractError("Cross-domain Session policy keys are not exact")
        if payload["schema_version"] != "okcanvas-cross-domain-session-delegation-policy-v1":
            raise CrossDomainSessionContractError("Cross-domain Session policy schema is unsupported")
        targets_raw = payload["targets"]
        if not isinstance(targets_raw, list) or len(targets_raw) != 2:
            raise CrossDomainSessionContractError("Cross-domain Session requires exactly two delegated read targets")
        targets: list[CrossDomainSessionTargetPolicy] = []
        keys = {
            "policy_id", "domain", "child_agent_id", "mcp_server_id", "child_output_contract", "max_result_bytes",
            "input_mode", "output_mode", "nested_stream_enabled", "inherit_parent_run_config",
        }
        for item in targets_raw:
            if not isinstance(item, dict) or set(item) != keys:
                raise CrossDomainSessionContractError("Cross-domain Session target keys are not exact")
            targets.append(CrossDomainSessionTargetPolicy(**item))
        if tuple(item.domain for item in targets) != ("GROUPWARE", "ORGANIZATION_CONTEXT"):
            raise CrossDomainSessionContractError("Cross-domain Session target order/domain drifted")
        if any(item.input_mode != "MODEL_GENERATED_TEXT" or item.output_mode != "BOUNDED_STRUCTURED_JSON" for item in targets):
            raise CrossDomainSessionContractError("Cross-domain Session child IO mode drifted")
        if any(not item.nested_stream_enabled or item.inherit_parent_run_config for item in targets):
            raise CrossDomainSessionContractError("Cross-domain Session child execution controls drifted")
        return CrossDomainSessionDelegationPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            root_agent_id=str(payload["root_agent_id"]),
            root_output_contract=str(payload["root_output_contract"]),
            root_session_mode=str(payload["root_session_mode"]),
            max_agent_tool_calls_per_turn=int(payload["max_agent_tool_calls_per_turn"]),
            max_depth=int(payload["max_depth"]),
            delegated_identity_required=bool(payload["delegated_identity_required"]),
            route_context_required=bool(payload["route_context_required"]),
            write_enabled=bool(payload["write_enabled"]),
            targets=tuple(targets),
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )
