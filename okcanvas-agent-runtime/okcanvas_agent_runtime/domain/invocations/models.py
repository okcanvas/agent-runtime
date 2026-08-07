from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class InvocationKind(StrEnum):
    ROOT = "ROOT"
    HANDOFF = "HANDOFF"
    AGENT_AS_TOOL = "AGENT_AS_TOOL"
    ORCHESTRATION_CHILD = "ORCHESTRATION_CHILD"


class InvocationState(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkspaceAccess(StrEnum):
    NONE = "none"
    ISOLATED = "isolated"
    SANDBOX_READONLY_V1 = "sandbox-readonly-v1"


@dataclass(frozen=True)
class InvocationPolicy:
    schema_version: str
    policy_id: str
    version: str
    max_depth: int
    max_handoffs_per_run: int
    max_agent_tools_per_run: int
    default_workspace_access: WorkspaceAccess
    physical_workspace_enabled: bool
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "max_depth": self.max_depth,
            "max_handoffs_per_run": self.max_handoffs_per_run,
            "max_agent_tools_per_run": self.max_agent_tools_per_run,
            "default_workspace_access": self.default_workspace_access.value,
            "physical_workspace_enabled": self.physical_workspace_enabled,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class ChildAgentEdge:
    parent_agent_id: str
    child_agent_id: str
    kind: InvocationKind
    depth: int
    child_definition_version: str
    child_definition_sha256: str
    workspace_access: WorkspaceAccess

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "parent_agent_id": self.parent_agent_id,
            "child_agent_id": self.child_agent_id,
            "kind": self.kind.value,
            "depth": self.depth,
            "child_definition_version": self.child_definition_version,
            "child_definition_sha256": self.child_definition_sha256,
            "workspace_access": self.workspace_access.value,
        }


@dataclass(frozen=True)
class AgentInvocationRecord:
    invocation_id: str
    run_id: str
    root_invocation_id: str
    parent_invocation_id: str | None
    invocation_kind: InvocationKind
    state: InvocationState
    agent_definition_id: str
    agent_definition_version: str
    agent_definition_sha256: str
    runtime_binding_sha256: str
    depth: int
    ordinal: int
    state_namespace: str
    workspace_access: WorkspaceAccess
    workspace_ref: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    created_at: str
    started_at: str | None
    completed_at: str | None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "invocation_id": self.invocation_id,
            "run_id": self.run_id,
            "root_invocation_id": self.root_invocation_id,
            "parent_invocation_id": self.parent_invocation_id,
            "invocation_kind": self.invocation_kind.value,
            "state": self.state.value,
            "agent_definition_id": self.agent_definition_id,
            "agent_definition_version": self.agent_definition_version,
            "agent_definition_sha256": self.agent_definition_sha256,
            "runtime_binding_sha256": self.runtime_binding_sha256,
            "depth": self.depth,
            "ordinal": self.ordinal,
            "state_namespace": self.state_namespace,
            "workspace_access": self.workspace_access.value,
            "workspace_ref": self.workspace_ref,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
