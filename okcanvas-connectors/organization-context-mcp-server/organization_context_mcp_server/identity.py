from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from hmac import compare_digest
from typing import Mapping

_TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_PRINCIPAL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}$")
_ROLE_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_DELEGATION_RE = re.compile(r"^delegation_[0-9a-f]{32}$")


class IdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class DelegatedIdentity:
    tenant_id: str
    principal_id: str
    roles: tuple[str, ...]
    delegation_id: str

    @classmethod
    def create(cls, *, tenant_id: str, principal_id: str, roles: tuple[str, ...]) -> "DelegatedIdentity":
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

    @classmethod
    def from_headers(cls, headers: Mapping[str, str], *, expected_bearer: str) -> "DelegatedIdentity":
        authorization = headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or not compare_digest(
            authorization[7:], expected_bearer
        ):
            raise IdentityError("Connector bearer authentication failed")
        tenant_id = headers.get("x-okcanvas-tenant-id", "").strip()
        principal_id = headers.get("x-okcanvas-principal-id", "").strip()
        roles_raw = headers.get("x-okcanvas-roles", "").strip()
        delegation_id = headers.get("x-okcanvas-delegation-id", "").strip()
        roles = tuple(item.strip() for item in roles_raw.split(",") if item.strip())
        if not _TENANT_RE.fullmatch(tenant_id):
            raise IdentityError("Delegated tenant ID is invalid")
        if not _PRINCIPAL_RE.fullmatch(principal_id):
            raise IdentityError("Delegated principal ID is invalid")
        if not roles or any(not _ROLE_RE.fullmatch(item) for item in roles):
            raise IdentityError("Delegated roles are invalid")
        if not _DELEGATION_RE.fullmatch(delegation_id):
            raise IdentityError("Delegation ID is invalid")
        expected = cls.create(tenant_id=tenant_id, principal_id=principal_id, roles=roles)
        if not compare_digest(expected.delegation_id, delegation_id):
            raise IdentityError("Delegation fingerprint does not match delegated identity")
        if "agent-user" not in expected.roles:
            raise IdentityError("Delegated principal lacks required role: agent-user")
        return expected
