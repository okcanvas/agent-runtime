"""Transport-neutral service client identity contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ServiceClientRole(StrEnum):
    AGENT_USER = "agent-user"
    APPROVAL_OPERATOR = "approval-operator"


@dataclass(frozen=True)
class ServicePrincipal:
    token_id: str
    tenant_id: str
    principal_id: str
    roles: frozenset[ServiceClientRole]

    def has_role(self, role: ServiceClientRole) -> bool:
        return role in self.roles

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-service-principal-v1",
            "token_id": self.token_id,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "roles": sorted(role.value for role in self.roles),
        }
