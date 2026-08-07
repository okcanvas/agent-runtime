from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity, MCPAccessCatalog

from .deployment import GroupwareDeploymentCatalog
from .models import (
    GroupwareReadOperation,
    GroupwareReadPolicy,
    GroupwareReadReadiness,
    GroupwareReadState,
)

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_TOOL_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class GroupwareReadContractError(RuntimeError):
    code = "GROUPWARE_READ_CONTRACT_INVALID"


class GroupwareReadCatalog:
    """Validate the first Product-owned Groupware read-only MCP vertical.

    The default pack intentionally retains a ``.invalid`` endpoint and no secret value. The
    vertical becomes executable only after an operator replaces the endpoint template with a real
    HTTPS endpoint and supplies the referenced environment secret.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "groupware" / "read-policy.json"
        self.policy = self._load_policy()
        self.deployment = GroupwareDeploymentCatalog(self.project_root)
        self._mcp = MCPServerCatalog(self.project_root)
        self._access = MCPAccessCatalog(self.project_root)
        self.server = self._validate_server_binding()
        if self.deployment.provider.allowed_tools != self.policy.allowed_tools:
            raise GroupwareReadContractError(
                "Groupware policy and external provider Tool contracts differ"
            )

    def readiness(self, identity: DelegatedMCPIdentity | None) -> GroupwareReadReadiness:
        parsed = urlsplit(self.server.url_template or "")
        endpoint_configured = bool(
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.hostname.endswith(".invalid")
            and "{tenant_id}" in (self.server.url_template or "")
        )
        credential = self._access.secret_references.get(self.server.credential_ref or "")
        credential_reference_configured = credential is not None
        raw_value = os.environ.get(credential.environment_variable, "") if credential else ""
        credential_value_configured = bool(raw_value.strip())
        identity_bound = identity is not None and bool(identity.tenant_id and identity.principal_id)
        role_allowed = bool(identity and set(self.policy.required_roles).intersection(identity.roles))

        reasons: list[str] = []
        if not endpoint_configured:
            reasons.append("groupware-endpoint-not-configured")
        if not credential_reference_configured:
            reasons.append("groupware-credential-reference-not-configured")
        if credential_reference_configured and not credential_value_configured:
            reasons.append("groupware-credential-value-not-configured")
        if not identity_bound:
            reasons.append("delegated-identity-required")
        if identity_bound and not role_allowed:
            reasons.append("delegated-role-not-allowed")

        if identity_bound and not role_allowed:
            state = GroupwareReadState.ACCESS_DENIED
        elif not reasons:
            # Reuse the exact STEP085 binding path before declaring readiness.
            self._access.bind_many((self.server,), identity)
            state = GroupwareReadState.READY
        else:
            state = GroupwareReadState.NOT_CONFIGURED
        return GroupwareReadReadiness(
            state=state,
            reasons=tuple(reasons),
            endpoint_configured=endpoint_configured,
            credential_reference_configured=credential_reference_configured,
            credential_value_configured=credential_value_configured,
            identity_bound=identity_bound,
            role_allowed=role_allowed,
        )

    def to_public_dict(self, identity: DelegatedMCPIdentity | None = None) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-groupware-read-foundation-v1",
            "policy": self.policy.to_public_dict(),
            "readiness": self.readiness(identity).to_public_dict(),
            "deployment": self.deployment.to_public_dict(),
            "server": {
                "server_id": self.server.server_id,
                "schema_version": self.server.schema_version,
                "read_only": self.server.read_only,
                "allowed_tools": list(self.server.allowed_tools),
                "authorization_mode": self.server.authorization_mode,
                "endpoint_mode": self.server.endpoint_mode,
                "credential_ref": self.server.credential_ref,
                "required_roles": list(self.server.required_roles),
                "secret_values_exposed": False,
            },
        }

    def _load_policy(self) -> GroupwareReadPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise GroupwareReadContractError("Groupware read policy is missing or unsafe")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GroupwareReadContractError("Groupware read policy is not valid UTF-8 JSON") from exc
        expected = {
            "schema_version", "policy_id", "version", "capability_id", "agent_id",
            "server_id", "required_roles", "operations", "max_results", "write_enabled",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise GroupwareReadContractError("Groupware read policy keys are not exact")
        if payload["schema_version"] != "okcanvas-groupware-read-policy-v1":
            raise GroupwareReadContractError("Groupware read policy schema is unsupported")
        if payload["write_enabled"] is not False:
            raise GroupwareReadContractError("Groupware write authority must remain disabled")
        required_roles = self._string_tuple(payload, "required_roles", _ID_RE)
        operations_raw = payload["operations"]
        if not isinstance(operations_raw, list) or not 1 <= len(operations_raw) <= 8:
            raise GroupwareReadContractError("Groupware read operations are invalid")
        operations: list[GroupwareReadOperation] = []
        for item in operations_raw:
            if not isinstance(item, dict) or set(item) != {"operation_id", "tool_name", "description"}:
                raise GroupwareReadContractError("Groupware read operation keys are not exact")
            operation_id = self._text(item, "operation_id")
            tool_name = self._text(item, "tool_name")
            description = self._text(item, "description")
            if not _ID_RE.fullmatch(operation_id) or not _TOOL_RE.fullmatch(tool_name):
                raise GroupwareReadContractError("Groupware read operation identifier is invalid")
            if any(token in tool_name for token in ("create", "update", "delete", "send", "post", "approve", "write")):
                raise GroupwareReadContractError("Groupware write-like Tool names are forbidden")
            operations.append(GroupwareReadOperation(operation_id, tool_name, description))
        tool_names = [item.tool_name for item in operations]
        if len(tool_names) != len(set(tool_names)):
            raise GroupwareReadContractError("Groupware read Tool names must be unique")
        maximum = payload["max_results"]
        if not isinstance(maximum, int) or isinstance(maximum, bool) or not 1 <= maximum <= 100:
            raise GroupwareReadContractError("Groupware max_results is invalid")
        return GroupwareReadPolicy(
            policy_id=self._id(payload, "policy_id"),
            version=self._text(payload, "version"),
            capability_id=self._id(payload, "capability_id"),
            agent_id=self._id(payload, "agent_id"),
            server_id=self._id(payload, "server_id"),
            required_roles=required_roles,
            operations=tuple(operations),
            max_results=maximum,
            policy_sha256=hashlib.sha256(raw).hexdigest(),
        )

    def _validate_server_binding(self):
        server = self._mcp.resolve(self.policy.server_id)
        if server.schema_version != "okcanvas-mcp-server-v3":
            raise GroupwareReadContractError("Groupware MCP server must use V3")
        if not server.is_remote_streamable_http or not server.read_only:
            raise GroupwareReadContractError("Groupware MCP server must be read-only remote HTTP")
        if not server.requires_delegated_identity or server.endpoint_mode != "tenant-template":
            raise GroupwareReadContractError("Groupware MCP server must use delegated tenant binding")
        if server.allowed_tools != self.policy.allowed_tools:
            raise GroupwareReadContractError("Groupware policy and MCP Tool allowlists differ")
        if server.required_roles != self.policy.required_roles:
            raise GroupwareReadContractError("Groupware policy and MCP role gates differ")
        if server.max_retry_attempts != 0:
            raise GroupwareReadContractError("Groupware read vertical must not retry remote calls")
        return server

    @staticmethod
    def _text(payload: dict[str, object], key: str) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise GroupwareReadContractError(f"{key} must be a non-empty string")
        return value.strip()

    @classmethod
    def _id(cls, payload: dict[str, object], key: str) -> str:
        value = cls._text(payload, key)
        if not _ID_RE.fullmatch(value):
            raise GroupwareReadContractError(f"{key} is invalid")
        return value

    @staticmethod
    def _string_tuple(payload: dict[str, object], key: str, pattern: re.Pattern[str]) -> tuple[str, ...]:
        value = payload[key]
        if not isinstance(value, list) or not value or any(
            not isinstance(item, str) or not pattern.fullmatch(item) for item in value
        ):
            raise GroupwareReadContractError(f"{key} is invalid")
        if len(value) != len(set(value)):
            raise GroupwareReadContractError(f"{key} contains duplicates")
        return tuple(value)
