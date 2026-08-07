from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog
from okcanvas_agent_runtime.agent.guardrails import GuardrailRuntimeCatalog
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.agent.skills import ProductSkillCatalog

from okcanvas_agent_runtime.agent.capabilities.topology.errors import CapabilityContractError
from okcanvas_agent_runtime.agent.capabilities.topology.models import AgentCapabilityTopology, CapabilityFoundationSnapshot, CapabilityActivation, CapabilityBinding, CapabilityFamily, CapabilityLoading
from okcanvas_agent_runtime.agent.capabilities.topology.policy import CapabilityDiscoveryPolicyCatalog

if TYPE_CHECKING:
    from okcanvas_agent_runtime.agent.definitions.models import AgentDefinition


def _canonical_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AgentCapabilityTopologyCatalog:
    """Normalize existing closed Agent declarations into one immutable capability topology.

    This foundation does not enable Tool Search, Programmatic Tool Calling, Shell, new hosted
    Tools, or dynamic discovery. It makes current and future surfaces explicit and runtime-bindable.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self._policy = CapabilityDiscoveryPolicyCatalog(self.project_root)
        self._function_tools = FunctionToolRuntimeCatalog(self.project_root)
        self._mcp = MCPServerCatalog(self.project_root)
        self._skills = ProductSkillCatalog(self.project_root)
        self._guardrails = GuardrailRuntimeCatalog(self.project_root)

    def resolve(self, definition: AgentDefinition) -> AgentCapabilityTopology:
        policy = self._policy.resolve()
        namespace_by_member = {
            member: namespace
            for namespace in policy.namespaces
            for member in namespace.member_ids
        }
        bindings: list[CapabilityBinding] = []

        for tool in self._function_tools.resolve_many(definition.tools):
            namespace = namespace_by_member.get(tool.tool_id)
            bindings.append(
                CapabilityBinding(
                    family=CapabilityFamily.TOOL,
                    kind="function-tool",
                    capability_id=tool.tool_id,
                    version=tool.runtime_version,
                    invocation_mode="sdk-function-tool",
                    sdk_surface="Agent.tools/FunctionTool",
                    activation=CapabilityActivation.ACTIVE,
                    loading=CapabilityLoading.EAGER,
                    namespace_id=namespace.namespace_id if namespace else None,
                    tool_search_eligible=True,
                    direct_call_allowed=True,
                    programmatic_call_allowed=False,
                    read_only=tool.read_only,
                    approval_mode=tool.approval_mode.value,
                    definition_sha256=tool.definition_sha256,
                )
            )

        for hosted_tool_id in definition.hosted_tools:
            if hosted_tool_id != "web-search-v1":
                raise CapabilityContractError("Unknown active hosted Tool capability")
            bindings.append(
                CapabilityBinding(
                    family=CapabilityFamily.TOOL,
                    kind="hosted-web-search",
                    capability_id=hosted_tool_id,
                    version="1.0.0",
                    invocation_mode="sdk-hosted-tool",
                    sdk_surface="Agent.tools/WebSearchTool",
                    activation=CapabilityActivation.ACTIVE,
                    loading=CapabilityLoading.EAGER,
                    namespace_id=None,
                    tool_search_eligible=False,
                    direct_call_allowed=True,
                    programmatic_call_allowed=False,
                    read_only=True,
                    approval_mode="NEVER",
                    definition_sha256=None,
                )
            )

        for server in self._mcp.resolve_many(definition.mcp_servers):
            bindings.append(
                CapabilityBinding(
                    family=CapabilityFamily.MCP,
                    kind=server.kind,
                    capability_id=server.server_id,
                    version=server.version,
                    invocation_mode="sdk-mcp-server",
                    sdk_surface="Agent.mcp_servers/MCPServer",
                    activation=CapabilityActivation.ACTIVE,
                    loading=CapabilityLoading.EAGER,
                    namespace_id=None,
                    tool_search_eligible=False,
                    direct_call_allowed=True,
                    programmatic_call_allowed=False,
                    read_only=server.read_only,
                    approval_mode="NEVER",
                    definition_sha256=server.definition_sha256,
                )
            )

        for skill in self._skills.resolve_many(definition.skills):
            bindings.append(
                CapabilityBinding(
                    family=CapabilityFamily.SKILL,
                    kind="product-instruction-skill",
                    capability_id=skill.skill_id,
                    version=skill.version,
                    invocation_mode="instruction-composition",
                    sdk_surface="Agent.instructions/Product-owned Skill",
                    activation=CapabilityActivation.ACTIVE,
                    loading=CapabilityLoading.INSTRUCTION_COMPOSED,
                    namespace_id=None,
                    tool_search_eligible=False,
                    direct_call_allowed=False,
                    programmatic_call_allowed=False,
                    read_only=True,
                    approval_mode=None,
                    definition_sha256=skill.package_sha256,
                )
            )

        for child_id in definition.handoffs:
            bindings.append(self._sub_agent(child_id, "handoff", "Agent.handoffs/Handoff"))
        for child_id in definition.agent_tools:
            bindings.append(
                self._sub_agent(child_id, "agent-as-tool", "Agent.as_tool/FunctionTool")
            )
        for child_id in definition.orchestration_children:
            bindings.append(
                self._sub_agent(
                    child_id,
                    "product-orchestration-child",
                    "Product orchestration/Runner.run",
                )
            )

        for guardrail in self._guardrails.resolve_many(definition.guardrails):
            bindings.append(
                CapabilityBinding(
                    family=CapabilityFamily.GUARDRAIL,
                    kind=guardrail.kind.value.lower().replace("_", "-"),
                    capability_id=guardrail.guardrail_id,
                    version=guardrail.version,
                    invocation_mode="sdk-guardrail",
                    sdk_surface=f"Agent.{guardrail.kind.value.lower()}_guardrails",
                    activation=CapabilityActivation.ACTIVE,
                    loading=CapabilityLoading.EAGER,
                    namespace_id=None,
                    tool_search_eligible=False,
                    direct_call_allowed=False,
                    programmatic_call_allowed=False,
                    read_only=True,
                    approval_mode=None,
                    definition_sha256=guardrail.definition_sha256,
                )
            )

        if definition.workspace_access != "none":
            bindings.append(
                CapabilityBinding(
                    family=CapabilityFamily.WORKSPACE,
                    kind=definition.workspace_access,
                    capability_id=definition.workspace_access,
                    version="1.0.0",
                    invocation_mode="product-workspace-binding",
                    sdk_surface="Product Sandbox Runtime",
                    activation=CapabilityActivation.ACTIVE,
                    loading=CapabilityLoading.OUT_OF_BAND,
                    namespace_id=None,
                    tool_search_eligible=False,
                    direct_call_allowed=False,
                    programmatic_call_allowed=False,
                    read_only=True,
                    approval_mode=None,
                    definition_sha256=None,
                )
            )
        if definition.input_mode != "text-only":
            bindings.append(
                CapabilityBinding(
                    family=CapabilityFamily.INPUT,
                    kind=definition.input_mode,
                    capability_id=definition.input_mode,
                    version="1.0.0",
                    invocation_mode="product-input-adapter",
                    sdk_surface="Runner input/Product attachment adapter",
                    activation=CapabilityActivation.ACTIVE,
                    loading=CapabilityLoading.OUT_OF_BAND,
                    namespace_id=None,
                    tool_search_eligible=False,
                    direct_call_allowed=False,
                    programmatic_call_allowed=False,
                    read_only=True,
                    approval_mode=None,
                    definition_sha256=None,
                )
            )
        if definition.session_mode != "disabled":
            bindings.append(
                CapabilityBinding(
                    family=CapabilityFamily.SESSION,
                    kind=definition.session_mode,
                    capability_id=definition.session_mode,
                    version="1.0.0",
                    invocation_mode="sdk-session",
                    sdk_surface="Runner.run/session",
                    activation=CapabilityActivation.ACTIVE,
                    loading=CapabilityLoading.OUT_OF_BAND,
                    namespace_id=None,
                    tool_search_eligible=False,
                    direct_call_allowed=False,
                    programmatic_call_allowed=False,
                    read_only=None,
                    approval_mode=None,
                    definition_sha256=None,
                )
            )

        keys = [(item.family.value, item.kind, item.capability_id) for item in bindings]
        if len(keys) != len(set(keys)):
            raise CapabilityContractError("Agent capability topology contains duplicate bindings")
        ordered = tuple(sorted(bindings, key=lambda item: (item.family.value, item.kind, item.capability_id)))
        active_namespace_ids = {
            item.namespace_id for item in ordered if item.namespace_id is not None
        }
        active_namespaces = tuple(
            namespace for namespace in policy.namespaces if namespace.namespace_id in active_namespace_ids
        )
        if any(item.loading is CapabilityLoading.DEFERRED for item in ordered):
            raise CapabilityContractError("STEP080 must not activate deferred Tool loading")
        if any(item.programmatic_call_allowed for item in ordered):
            raise CapabilityContractError("STEP080 must not activate programmatic Tool callers")
        payload = {
            "schema_version": "okcanvas-agent-capability-topology-v1",
            "agent_id": definition.agent_id,
            "bindings": [item.to_public_dict() for item in ordered],
            "namespaces": [item.to_public_dict() for item in active_namespaces],
            "discovery_policy_sha256": policy.policy_sha256,
        }
        return AgentCapabilityTopology(
            schema_version="okcanvas-agent-capability-topology-v1",
            agent_id=definition.agent_id,
            bindings=ordered,
            namespaces=active_namespaces,
            discovery_policy=policy,
            topology_sha256=_canonical_sha(payload),
        )

    @staticmethod
    def _sub_agent(child_id: str, kind: str, sdk_surface: str) -> CapabilityBinding:
        return CapabilityBinding(
            family=CapabilityFamily.SUB_AGENT,
            kind=kind,
            capability_id=child_id,
            version="definition-bound",
            invocation_mode=kind,
            sdk_surface=sdk_surface,
            activation=CapabilityActivation.ACTIVE,
            loading=CapabilityLoading.EAGER,
            namespace_id=None,
            tool_search_eligible=False,
            direct_call_allowed=kind == "agent-as-tool",
            programmatic_call_allowed=False,
            read_only=None,
            approval_mode="NEVER" if kind == "agent-as-tool" else None,
            definition_sha256=None,
        )


class CapabilityFoundationCatalog:
    """Resolve the complete immutable capability extension foundation for this package."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self._topologies = AgentCapabilityTopologyCatalog(self.project_root)
        self._policy = CapabilityDiscoveryPolicyCatalog(self.project_root)

    def resolve(self) -> CapabilityFoundationSnapshot:
        from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog

        definitions = AgentDefinitionCatalog(self.project_root).list_definitions()
        topologies = tuple(self._topologies.resolve(definition) for definition in definitions)
        policy = self._policy.resolve()
        from okcanvas_agent_runtime.agent.capabilities.topology.examples import SDKExampleCatalog

        examples = SDKExampleCatalog(self.project_root).resolve()
        family_counts: dict[str, int] = {}
        kind_counts: dict[str, int] = {}
        binding_count = 0
        for topology in topologies:
            for binding in topology.bindings:
                binding_count += 1
                family_counts[binding.family.value] = family_counts.get(binding.family.value, 0) + 1
                kind_key = f"{binding.family.value}/{binding.kind}"
                kind_counts[kind_key] = kind_counts.get(kind_key, 0) + 1
        payload = {
            "schema_version": "okcanvas-capability-foundation-v1",
            "agent_topologies": [
                {"agent_id": topology.agent_id, "topology_sha256": topology.topology_sha256}
                for topology in topologies
            ],
            "binding_count": binding_count,
            "family_counts": dict(sorted(family_counts.items())),
            "kind_counts": dict(sorted(kind_counts.items())),
            "discovery_policy_sha256": policy.policy_sha256,
            "sdk_example_inventory_sha256": examples.inventory_sha256,
        }
        return CapabilityFoundationSnapshot(
            schema_version="okcanvas-capability-foundation-v1",
            agent_topology_count=len(topologies),
            binding_count=binding_count,
            family_counts=tuple(sorted(family_counts.items())),
            kind_counts=tuple(sorted(kind_counts.items())),
            discovery_policy=policy,
            sdk_example_inventory=examples,
            topology_root_sha256=_canonical_sha(payload),
        )
