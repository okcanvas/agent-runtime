from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class DelegatedMCPIdentity:
    tenant_id: str
    principal_id: str
    roles: tuple[str, ...]
    delegation_id: str

    @classmethod
    def create(cls, *, tenant_id: str, principal_id: str, roles: tuple[str, ...]) -> "DelegatedMCPIdentity":
        normalized_roles = tuple(sorted(set(roles)))
        payload = json.dumps(
            {"tenant_id": tenant_id, "principal_id": principal_id, "roles": normalized_roles},
            sort_keys=True,
            separators=(",", ":"),
        )
        return cls(
            tenant_id=tenant_id,
            principal_id=principal_id,
            roles=normalized_roles,
            delegation_id="delegation_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32],
        )

    def to_protected_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-delegated-mcp-identity-v1",
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "roles": list(self.roles),
            "delegation_id": self.delegation_id,
        }

    @classmethod
    def from_protected_dict(cls, payload: dict[str, object]) -> "DelegatedMCPIdentity":
        if set(payload) != {"schema_version", "tenant_id", "principal_id", "roles", "delegation_id"}:
            raise ValueError("Delegated MCP identity keys are invalid")
        if payload["schema_version"] != "okcanvas-delegated-mcp-identity-v1":
            raise ValueError("Delegated MCP identity schema is invalid")
        tenant_id = payload["tenant_id"]
        principal_id = payload["principal_id"]
        roles = payload["roles"]
        delegation_id = payload["delegation_id"]
        if not isinstance(tenant_id, str) or not tenant_id or not isinstance(principal_id, str) or not principal_id:
            raise ValueError("Delegated MCP identity subject is invalid")
        if not isinstance(roles, list) or any(not isinstance(item, str) or not item for item in roles):
            raise ValueError("Delegated MCP identity roles are invalid")
        expected = cls.create(tenant_id=tenant_id, principal_id=principal_id, roles=tuple(roles))
        if delegation_id != expected.delegation_id:
            raise ValueError("Delegated MCP identity fingerprint is invalid")
        return expected


@dataclass(frozen=True)
class MCPSecretReference:
    credential_ref: str
    authorization_mode: str
    environment_variable: str

    def to_public_dict(self) -> dict[str, str]:
        return {
            "credential_ref": self.credential_ref,
            "authorization_mode": self.authorization_mode,
            "environment_variable": self.environment_variable,
        }


@dataclass(frozen=True)
class MCPAccessPolicy:
    policy_id: str
    version: str
    max_remote_servers_per_agent: int
    endpoint_mode: str
    delegated_headers: tuple[str, ...]
    health_mode: str
    circuit_breaker_state_scope: str
    policy_sha256: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-mcp-access-policy-v1",
            "policy_id": self.policy_id,
            "version": self.version,
            "max_remote_servers_per_agent": self.max_remote_servers_per_agent,
            "endpoint_mode": self.endpoint_mode,
            "delegated_headers": list(self.delegated_headers),
            "health_mode": self.health_mode,
            "circuit_breaker_state_scope": self.circuit_breaker_state_scope,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class BoundMCPAccess:
    server_id: str
    url: str
    credential_ref: str
    credential_environment_variable: str
    identity: DelegatedMCPIdentity
    required_roles: tuple[str, ...]
    health_mode: str
    circuit_breaker_failure_threshold: int
    circuit_breaker_reset_seconds: float

    def identity_headers(self) -> dict[str, str]:
        return {
            "X-OKCanvas-Tenant-ID": self.identity.tenant_id,
            "X-OKCanvas-Principal-ID": self.identity.principal_id,
            "X-OKCanvas-Roles": ",".join(self.identity.roles),
            "X-OKCanvas-Delegation-ID": self.identity.delegation_id,
        }

    def to_public_dict(self) -> dict[str, object]:
        return {
            "server_id": self.server_id,
            "url": self.url,
            "credential_ref": self.credential_ref,
            "required_roles": list(self.required_roles),
            "delegation_id": self.identity.delegation_id,
            "health_mode": self.health_mode,
            "circuit_breaker_failure_threshold": self.circuit_breaker_failure_threshold,
            "circuit_breaker_reset_seconds": self.circuit_breaker_reset_seconds,
        }
