# CONNECTOR-ISSUE-001 — Delegated roles were declared but not transmitted

STEP086R1 required `roles` in the external provider identity contract, while Runtime
`BoundMCPAccess.identity_headers()` transmitted only tenant, principal and delegation ID. A real
Connector could not verify required roles or recompute the delegation fingerprint.

The closure is Runtime STEP086R2 adding canonical `X-OKCanvas-Roles` plus this Connector requiring
and validating it before any downstream call. Regression tests mutate roles/principal and prove the
request fails before Groupware API access.
