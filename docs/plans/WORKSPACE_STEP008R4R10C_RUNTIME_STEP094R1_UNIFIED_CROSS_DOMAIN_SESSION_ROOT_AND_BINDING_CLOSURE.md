# WORKSPACE STEP008R4R10C / Runtime STEP094R1

Current Workspace: WORKSPACE_STEP008R4R10C_RUNTIME_STEP094R1_UNIFIED_CROSS_DOMAIN_SESSION_ROOT_AND_BINDING_CLOSURE
Workspace Version: 0.8.4-r10c
Current Runtime: STEP094R1_UNIFIED_CROSS_DOMAIN_SESSION_ROOT_AND_BINDING_CLOSURE
Runtime Version: 2.78.1

## Purpose

Close the real Windows STEP094 first-Turn admission failure by making cross-domain conversation ownership
match the immutable Session binding instead of changing or bypassing Session identity.

## Product changes

- `organization-assistant-session-agent` v1.2.0 is the canonical cross-domain Session root.
- It declares exactly `groupware-read-agent` and `organization-context-read-agent` as stateless children.
- `cross-domain-session-delegation-policy.json` binds both children, output contracts, MCP servers and limits.
- Immutable routing context selects exactly one delegated read domain per Turn.
- Runtime binding uses `sqlite-session-bounded-cross-domain-read-subagent-execution-v1` and hashes both child/MCP owners.
- Organization Context current read policy uses the unified Session root.
- Service/Admin route paths fail closed if an executable selected Agent differs from the supplied Session's bound Agent.

## Non-goals

- no Session-ID switching;
- no focus copy/migration between Session records;
- no Agent-ID alias/fallback;
- no label/name fallback;
- no Groupware or Organization authorization weakening;
- no MinIO/Object Storage work.

## Validation state

Executable unit/deterministic/full-regression tests were not run in this packaging environment. Static
contract, current SOT, launcher registry and architecture validation are prepared; the same focused Windows
cross-domain Live gate must be rerun before promotion.
