from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GroupwareReadState(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    READY = "READY"
    ACCESS_DENIED = "ACCESS_DENIED"


@dataclass(frozen=True)
class GroupwareReadOperation:
    operation_id: str
    tool_name: str
    description: str

    def to_public_dict(self) -> dict[str, str]:
        return {
            "operation_id": self.operation_id,
            "tool_name": self.tool_name,
            "description": self.description,
        }


@dataclass(frozen=True)
class GroupwareReadPolicy:
    policy_id: str
    version: str
    capability_id: str
    agent_id: str
    server_id: str
    required_roles: tuple[str, ...]
    operations: tuple[GroupwareReadOperation, ...]
    max_results: int
    policy_sha256: str

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        return tuple(item.tool_name for item in self.operations)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-groupware-read-policy-v1",
            "policy_id": self.policy_id,
            "version": self.version,
            "capability_id": self.capability_id,
            "agent_id": self.agent_id,
            "server_id": self.server_id,
            "required_roles": list(self.required_roles),
            "operations": [item.to_public_dict() for item in self.operations],
            "max_results": self.max_results,
            "write_enabled": False,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class GroupwareReadReadiness:
    state: GroupwareReadState
    reasons: tuple[str, ...]
    endpoint_configured: bool
    credential_reference_configured: bool
    credential_value_configured: bool
    identity_bound: bool
    role_allowed: bool

    @property
    def executable_now(self) -> bool:
        return self.state is GroupwareReadState.READY

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-groupware-read-readiness-v1",
            "state": self.state.value,
            "reasons": list(self.reasons),
            "endpoint_configured": self.endpoint_configured,
            "credential_reference_configured": self.credential_reference_configured,
            "credential_value_configured": self.credential_value_configured,
            "identity_bound": self.identity_bound,
            "role_allowed": self.role_allowed,
            "executable_now": self.executable_now,
            "write_enabled": False,
        }
