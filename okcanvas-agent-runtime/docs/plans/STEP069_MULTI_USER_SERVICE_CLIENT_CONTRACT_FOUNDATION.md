# STEP069 Multi-user Service Client Contract Foundation

- Version: `2.49.0`
- STEP: `STEP069_MULTI_USER_SERVICE_CLIENT_CONTRACT_FOUNDATION`
- Predecessor: STEP068 Windows-live accepted 30/30

## Goal

Correct the product boundary before Skill and UI work: OKCanvas Agent Runtime is a multi-user server,
while the current TUI, `/runner`, `/console` and Node CLI are development/acceptance harnesses.
Provide one additive service API contract that future `agent-cli`, `agent-web` and `agent-desktop`
applications can consume without importing Runtime code or accessing server storage.

## Scope

1. External Bearer token registry with hashes only.
2. Immutable tenant/principal/role identity.
3. Additive SQLite resource-ownership projection.
4. Principal-scoped Session, Attachment, Submission, Run, Event, Invocation and Artifact APIs.
5. Tenant-scoped separate Approval Operator APIs.
6. Principal-namespaced Submission idempotency.
7. Persisted SSE with `Last-Event-ID` as the service stream.
8. Multi-Artifact list and verified Artifact detail.
9. Service capability and error-contract discovery.
10. Explicit development-harness and future-client repository separation.

## Exclusions

- OIDC/OAuth/JWT issuer integration;
- user provisioning and password login;
- tenant administration UI;
- distributed databases or workers;
- service `agent-cli`, `agent-web` or `agent-desktop` implementation;
- native SDK stream exposure;
- direct Runtime SQLite/workspace access;
- Skill runtime implementation.

## Next step

`STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1` is selected only after STEP069 Windows closure.
