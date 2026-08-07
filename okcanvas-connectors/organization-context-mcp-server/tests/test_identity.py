from organization_context_mcp_server.identity import DelegatedIdentity, IdentityError


def test_delegated_identity_round_trip() -> None:
    identity = DelegatedIdentity.create(
        tenant_id="tenant-a", principal_id="user-001", roles=("employee", "agent-user")
    )
    parsed = DelegatedIdentity.from_headers(
        {
            "authorization": "Bearer connector-secret",
            "x-okcanvas-tenant-id": identity.tenant_id,
            "x-okcanvas-principal-id": identity.principal_id,
            "x-okcanvas-roles": ",".join(identity.roles),
            "x-okcanvas-delegation-id": identity.delegation_id,
        },
        expected_bearer="connector-secret",
    )
    assert parsed == identity


def test_required_agent_user_role_is_enforced() -> None:
    identity = DelegatedIdentity.create(
        tenant_id="tenant-a", principal_id="user-001", roles=("employee",)
    )
    try:
        DelegatedIdentity.from_headers(
            {
                "authorization": "Bearer connector-secret",
                "x-okcanvas-tenant-id": identity.tenant_id,
                "x-okcanvas-principal-id": identity.principal_id,
                "x-okcanvas-roles": ",".join(identity.roles),
                "x-okcanvas-delegation-id": identity.delegation_id,
            },
            expected_bearer="connector-secret",
        )
    except IdentityError as exc:
        assert "agent-user" in str(exc)
    else:
        raise AssertionError("missing required-role rejection")
