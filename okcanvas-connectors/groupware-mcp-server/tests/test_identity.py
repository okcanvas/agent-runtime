from __future__ import annotations

import pytest

from groupware_mcp_server.identity import DelegatedIdentity, IdentityError


def headers(identity: DelegatedIdentity, token: str = "connector-secret") -> dict[str, str]:
    return {
        "authorization": f"Bearer {token}",
        "x-okcanvas-tenant-id": identity.tenant_id,
        "x-okcanvas-principal-id": identity.principal_id,
        "x-okcanvas-roles": ",".join(identity.roles),
        "x-okcanvas-delegation-id": identity.delegation_id,
    }


def test_delegated_identity_round_trip_and_role_validation() -> None:
    identity = DelegatedIdentity.create(
        tenant_id="tenant-a", principal_id="user-001", roles=("agent-user", "employee")
    )
    assert DelegatedIdentity.from_headers(headers(identity), expected_bearer="connector-secret") == identity


def test_missing_role_or_fingerprint_drift_is_rejected() -> None:
    denied = DelegatedIdentity.create(tenant_id="tenant-a", principal_id="user-001", roles=("employee",))
    with pytest.raises(IdentityError, match="required role"):
        DelegatedIdentity.from_headers(headers(denied), expected_bearer="connector-secret")
    allowed = DelegatedIdentity.create(tenant_id="tenant-a", principal_id="user-001", roles=("agent-user",))
    altered = headers(allowed)
    altered["x-okcanvas-principal-id"] = "user-002"
    with pytest.raises(IdentityError, match="fingerprint"):
        DelegatedIdentity.from_headers(altered, expected_bearer="connector-secret")
