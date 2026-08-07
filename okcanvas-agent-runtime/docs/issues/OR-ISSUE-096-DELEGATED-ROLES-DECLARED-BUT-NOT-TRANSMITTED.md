# OR-ISSUE-096 — Delegated roles were declared but not transmitted

## Failure

STEP086R1 required external Groupware providers to receive `tenant_id`, `principal_id`, `roles` and
`delegation_id`, but `BoundMCPAccess.identity_headers()` emitted only tenant, principal and
delegation headers. A real external Connector could not enforce required roles or recompute the
identity fingerprint from the transmitted context.

## Root cause

The provider contract and the actual remote HTTP header policy evolved separately. Deterministic
fixtures contained `roles`, which masked that the runtime transport omitted them.

## Correction

STEP086R2 adds canonical `X-OKCanvas-Roles`, sorts and joins normalized roles deterministically,
updates the access policy and provider contract, and verifies the external Connector path
`okcanvas-connectors/groupware-mcp-server`. Credential references remain Runtime-internal and are
not transmitted.

## Recurrence gate

- exact delegated header set validation;
- `BoundMCPAccess.identity_headers()` role assertion;
- external Connector recomputes and verifies the delegation fingerprint;
- connector/example cross-project integration checks downstream role forwarding.
