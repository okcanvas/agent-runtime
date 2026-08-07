from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class CapabilityFamily(StrEnum):
    TOOL = "tool"
    SKILL = "skill"
    SUB_AGENT = "sub-agent"
    MCP = "mcp"
    GUARDRAIL = "guardrail"
    WORKSPACE = "workspace"
    INPUT = "input"
    SESSION = "session"


class CapabilityActivation(StrEnum):
    ACTIVE = "ACTIVE"
    STRUCTURE_ONLY = "STRUCTURE_ONLY"
    DISABLED = "DISABLED"


class CapabilityLoading(StrEnum):
    EAGER = "EAGER"
    DEFERRED = "DEFERRED"
    INSTRUCTION_COMPOSED = "INSTRUCTION_COMPOSED"
    OUT_OF_BAND = "OUT_OF_BAND"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class CapabilityNamespace:
    namespace_id: str
    description: str
    member_ids: tuple[str, ...]
    loading: CapabilityLoading
    activation: CapabilityActivation

    def to_public_dict(self) -> dict[str, object]:
        return {
            "namespace_id": self.namespace_id,
            "description": self.description,
            "member_ids": list(self.member_ids),
            "loading": self.loading.value,
            "activation": self.activation.value,
        }


@dataclass(frozen=True)
class CapabilityBinding:
    family: CapabilityFamily
    kind: str
    capability_id: str
    version: str
    invocation_mode: str
    sdk_surface: str
    activation: CapabilityActivation
    loading: CapabilityLoading
    namespace_id: str | None
    tool_search_eligible: bool
    direct_call_allowed: bool
    programmatic_call_allowed: bool
    read_only: bool | None
    approval_mode: str | None
    definition_sha256: str | None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "kind": self.kind,
            "capability_id": self.capability_id,
            "version": self.version,
            "invocation_mode": self.invocation_mode,
            "sdk_surface": self.sdk_surface,
            "activation": self.activation.value,
            "loading": self.loading.value,
            "namespace_id": self.namespace_id,
            "tool_search_eligible": self.tool_search_eligible,
            "direct_call_allowed": self.direct_call_allowed,
            "programmatic_call_allowed": self.programmatic_call_allowed,
            "read_only": self.read_only,
            "approval_mode": self.approval_mode,
            "definition_sha256": self.definition_sha256,
        }


@dataclass(frozen=True)
class CapabilityDiscoveryPolicy:
    schema_version: str
    policy_id: str
    version: str
    sdk_package: str
    sdk_version: str
    tool_search_runtime_enabled: bool
    tool_search_execution: str
    max_namespaces_per_agent: int
    max_deferred_tools_per_agent: int
    allowed_tool_search_surface_kinds: tuple[str, ...]
    programmatic_tool_calling_runtime_enabled: bool
    default_allowed_callers: tuple[str, ...]
    max_programmatic_callable_tools: int
    namespaces: tuple[CapabilityNamespace, ...]
    policy_sha256: str
    path: Path

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "sdk_package": self.sdk_package,
            "sdk_version": self.sdk_version,
            "tool_search_runtime_enabled": self.tool_search_runtime_enabled,
            "tool_search_execution": self.tool_search_execution,
            "max_namespaces_per_agent": self.max_namespaces_per_agent,
            "max_deferred_tools_per_agent": self.max_deferred_tools_per_agent,
            "allowed_tool_search_surface_kinds": list(self.allowed_tool_search_surface_kinds),
            "programmatic_tool_calling_runtime_enabled": self.programmatic_tool_calling_runtime_enabled,
            "default_allowed_callers": list(self.default_allowed_callers),
            "max_programmatic_callable_tools": self.max_programmatic_callable_tools,
            "namespaces": [item.to_public_dict() for item in self.namespaces],
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class AgentCapabilityTopology:
    schema_version: str
    agent_id: str
    bindings: tuple[CapabilityBinding, ...]
    namespaces: tuple[CapabilityNamespace, ...]
    discovery_policy: CapabilityDiscoveryPolicy
    topology_sha256: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "bindings": [item.to_public_dict() for item in self.bindings],
            "namespaces": [item.to_public_dict() for item in self.namespaces],
            "discovery_policy": self.discovery_policy.to_public_dict(),
            "topology_sha256": self.topology_sha256,
        }


@dataclass(frozen=True)
class SDKExampleRecord:
    example_id: str
    relative_path: str
    family: CapabilityFamily
    pattern: str
    product_status: CapabilityActivation
    rationale: str
    sha256: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "example_id": self.example_id,
            "relative_path": self.relative_path,
            "family": self.family.value,
            "pattern": self.pattern,
            "product_status": self.product_status.value,
            "rationale": self.rationale,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class SDKExampleInventory:
    schema_version: str
    sdk_package: str
    sdk_version: str
    records: tuple[SDKExampleRecord, ...]
    inventory_sha256: str
    manifest_path: Path

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sdk_package": self.sdk_package,
            "sdk_version": self.sdk_version,
            "records": [item.to_public_dict() for item in self.records],
            "inventory_sha256": self.inventory_sha256,
        }


@dataclass(frozen=True)
class CapabilityFoundationSnapshot:
    schema_version: str
    agent_topology_count: int
    binding_count: int
    family_counts: tuple[tuple[str, int], ...]
    kind_counts: tuple[tuple[str, int], ...]
    discovery_policy: CapabilityDiscoveryPolicy
    sdk_example_inventory: SDKExampleInventory
    topology_root_sha256: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "agent_topology_count": self.agent_topology_count,
            "binding_count": self.binding_count,
            "family_counts": {key: value for key, value in self.family_counts},
            "kind_counts": {key: value for key, value in self.kind_counts},
            "discovery_policy": self.discovery_policy.to_public_dict(),
            "sdk_example_inventory": {
                "schema_version": self.sdk_example_inventory.schema_version,
                "sdk_package": self.sdk_example_inventory.sdk_package,
                "sdk_version": self.sdk_example_inventory.sdk_version,
                "record_count": len(self.sdk_example_inventory.records),
                "inventory_sha256": self.sdk_example_inventory.inventory_sha256,
            },
            "topology_root_sha256": self.topology_root_sha256,
        }
