from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerDefinition
from okcanvas_agent_runtime.application.mcp_access.models import (
    BoundMCPAccess,
    DelegatedMCPIdentity,
    MCPAccessPolicy,
    MCPSecretReference,
)

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_TENANT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


class MCPAccessContractError(RuntimeError):
    pass


class MCPAccessCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.root = (self.project_root / "specs" / "mcp" / "access").resolve()
        self.policy = self._load_policy()
        self.secret_references = self._load_secret_references()

    def bind_many(
        self,
        definitions: tuple[MCPServerDefinition, ...],
        identity: DelegatedMCPIdentity | None,
    ) -> tuple[BoundMCPAccess | None, ...]:
        remote = tuple(item for item in definitions if item.is_remote_streamable_http)
        if len(remote) > self.policy.max_remote_servers_per_agent:
            raise MCPAccessContractError("Remote MCP server count exceeds access policy")
        bindings: list[BoundMCPAccess | None] = []
        for definition in definitions:
            if not definition.requires_delegated_identity:
                bindings.append(None)
                continue
            if identity is None:
                raise MCPAccessContractError("Delegated MCP identity is required")
            if not _TENANT_RE.fullmatch(identity.tenant_id):
                raise MCPAccessContractError("Delegated tenant ID is invalid for endpoint binding")
            if not set(definition.required_roles).intersection(identity.roles):
                raise MCPAccessContractError("Delegated principal lacks a required MCP role")
            if not definition.url_template or not definition.credential_ref:
                raise MCPAccessContractError("Delegated MCP definition is incomplete")
            secret = self.secret_references.get(definition.credential_ref)
            if secret is None:
                raise MCPAccessContractError("MCP credential reference is not configured")
            url = definition.url_template.replace("{tenant_id}", identity.tenant_id)
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment or parsed.username:
                raise MCPAccessContractError("Resolved delegated MCP URL is unsafe")
            bindings.append(
                BoundMCPAccess(
                    server_id=definition.server_id,
                    url=url,
                    credential_ref=secret.credential_ref,
                    credential_environment_variable=secret.environment_variable,
                    identity=identity,
                    required_roles=definition.required_roles,
                    health_mode=definition.health_mode,
                    circuit_breaker_failure_threshold=definition.circuit_breaker_failure_threshold,
                    circuit_breaker_reset_seconds=definition.circuit_breaker_reset_seconds,
                )
            )
        return tuple(bindings)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-mcp-access-catalog-v1",
            "policy": self.policy.to_public_dict(),
            "credential_references": [
                item.to_public_dict() for item in sorted(self.secret_references.values(), key=lambda x: x.credential_ref)
            ],
            "credential_values_exposed": False,
        }

    def _load_policy(self) -> MCPAccessPolicy:
        path = self.root / "access-policy.json"
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        expected = {
            "schema_version", "policy_id", "version", "max_remote_servers_per_agent",
            "endpoint_mode", "delegated_headers", "health_mode", "circuit_breaker_state_scope",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise MCPAccessContractError("MCP access policy keys are invalid")
        if payload["schema_version"] != "okcanvas-mcp-access-policy-v1":
            raise MCPAccessContractError("MCP access policy schema is invalid")
        if payload["endpoint_mode"] != "tenant-template" or payload["health_mode"] != "passive":
            raise MCPAccessContractError("MCP access policy mode is unsupported")
        maximum = payload["max_remote_servers_per_agent"]
        if not isinstance(maximum, int) or not 1 <= maximum <= 4:
            raise MCPAccessContractError("MCP access policy server limit is invalid")
        headers = payload["delegated_headers"]
        required = {
            "X-OKCanvas-Tenant-ID",
            "X-OKCanvas-Principal-ID",
            "X-OKCanvas-Roles",
            "X-OKCanvas-Delegation-ID",
        }
        if not isinstance(headers, list) or set(headers) != required:
            raise MCPAccessContractError("MCP delegated header policy is invalid")
        return MCPAccessPolicy(
            policy_id=str(payload["policy_id"]), version=str(payload["version"]),
            max_remote_servers_per_agent=maximum, endpoint_mode=str(payload["endpoint_mode"]),
            delegated_headers=tuple(sorted(headers)), health_mode=str(payload["health_mode"]),
            circuit_breaker_state_scope=str(payload["circuit_breaker_state_scope"]),
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )

    def _load_secret_references(self) -> dict[str, MCPSecretReference]:
        path = self.root / "credential-references.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "references"}:
            raise MCPAccessContractError("MCP credential reference catalog is invalid")
        if payload["schema_version"] != "okcanvas-mcp-credential-references-v1" or not isinstance(payload["references"], list):
            raise MCPAccessContractError("MCP credential reference schema is invalid")
        result: dict[str, MCPSecretReference] = {}
        for item in payload["references"]:
            if not isinstance(item, dict) or set(item) != {"credential_ref", "authorization_mode", "environment_variable"}:
                raise MCPAccessContractError("MCP credential reference entry is invalid")
            ref = item["credential_ref"]
            env = item["environment_variable"]
            if not isinstance(ref, str) or not _ID_RE.fullmatch(ref) or ref in result:
                raise MCPAccessContractError("MCP credential reference ID is invalid")
            if item["authorization_mode"] != "delegated-bearer-ref" or not isinstance(env, str) or not _ENV_RE.fullmatch(env):
                raise MCPAccessContractError("MCP credential reference mode is invalid")
            result[ref] = MCPSecretReference(ref, "delegated-bearer-ref", env)
        return result
