from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any

from fastapi import Header

from okcanvas_agent_runtime.application.errors import ControlAPIError

from okcanvas_agent_runtime.core.service_identity import ServiceClientRole, ServicePrincipal

_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class _RegistryEntry:
    token_sha256: str
    principal: ServicePrincipal


class ServiceClientTokenRegistry:
    schema_version = "okcanvas-service-client-token-registry-v1"

    def __init__(self, entries: tuple[_RegistryEntry, ...]) -> None:
        if not entries:
            raise ValueError("Service client token registry must contain at least one token")
        token_ids = [entry.principal.token_id for entry in entries]
        token_hashes = [entry.token_sha256 for entry in entries]
        if len(set(token_ids)) != len(token_ids) or len(set(token_hashes)) != len(token_hashes):
            raise ValueError("Service client token registry identities must be unique")
        self._entries = entries

    @classmethod
    def from_json_text(cls, raw: str) -> "ServiceClientTokenRegistry":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Service client token registry is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "tokens"}:
            raise ValueError("Service client token registry fields are invalid")
        if payload["schema_version"] != cls.schema_version or not isinstance(payload["tokens"], list):
            raise ValueError("Service client token registry schema is invalid")
        entries: list[_RegistryEntry] = []
        for item in payload["tokens"]:
            if not isinstance(item, dict) or set(item) != {
                "token_id", "token_sha256", "tenant_id", "principal_id", "roles"
            }:
                raise ValueError("Service client token entry fields are invalid")
            token_id = item["token_id"]
            token_sha256 = item["token_sha256"]
            tenant_id = item["tenant_id"]
            principal_id = item["principal_id"]
            roles_raw = item["roles"]
            if not all(isinstance(value, str) and _ID_RE.fullmatch(value) for value in (token_id, tenant_id, principal_id)):
                raise ValueError("Service client token identity is invalid")
            if not isinstance(token_sha256, str) or _SHA_RE.fullmatch(token_sha256) is None:
                raise ValueError("Service client token SHA-256 is invalid")
            if not isinstance(roles_raw, list) or not roles_raw:
                raise ValueError("Service client token roles are invalid")
            try:
                roles = frozenset(ServiceClientRole(str(value)) for value in roles_raw)
            except ValueError as exc:
                raise ValueError("Service client token role is unsupported") from exc
            if len(roles) != len(roles_raw):
                raise ValueError("Service client token roles must be unique")
            entries.append(_RegistryEntry(
                token_sha256=token_sha256,
                principal=ServicePrincipal(
                    token_id=token_id,
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    roles=roles,
                ),
            ))
        return cls(tuple(entries))

    def authenticate(self, token: str) -> ServicePrincipal | None:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        match: ServicePrincipal | None = None
        for entry in self._entries:
            if hmac.compare_digest(digest, entry.token_sha256):
                match = entry.principal
        return match


class ServiceClientAuthenticator:
    def __init__(self, registry: ServiceClientTokenRegistry | None) -> None:
        self._registry = registry

    @property
    def configured(self) -> bool:
        return self._registry is not None

    async def require(
        self,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> ServicePrincipal:
        if self._registry is None:
            raise ControlAPIError(
                503,
                "SERVICE_CLIENT_AUTH_NOT_CONFIGURED",
                "Service client authentication is not configured on this server",
            )
        if authorization is None or not authorization.startswith("Bearer "):
            raise ControlAPIError(401, "SERVICE_CLIENT_AUTH_REQUIRED", "A Bearer service token is required")
        token = authorization[7:]
        if not token or len(token) > 512 or any(character in token for character in "\r\n\x00"):
            raise ControlAPIError(401, "SERVICE_CLIENT_AUTH_REQUIRED", "A valid Bearer service token is required")
        principal = self._registry.authenticate(token)
        if principal is None:
            raise ControlAPIError(401, "SERVICE_CLIENT_AUTH_INVALID", "The Bearer service token is invalid")
        return principal

    @staticmethod
    def require_role(principal: ServicePrincipal, role: ServiceClientRole) -> ServicePrincipal:
        if not principal.has_role(role):
            raise ControlAPIError(
                403,
                "SERVICE_CLIENT_ROLE_REQUIRED",
                f"Service client role is required: {role.value}",
            )
        return principal
