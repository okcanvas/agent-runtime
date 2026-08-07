# Groupware Sub-agent and MCP deployment boundary

## Decision

The Product-owned Groupware read Sub-agent stays inside the Runtime source/specification boundary. The actual organization Groupware MCP provider is deployed outside the Runtime as a separate connector service.

```text
OKCanvas Agent Runtime
├─ specs/agents/groupware-read-agent       Product-owned Sub-agent
├─ GroupwareReadResult                     Product-owned final-output safety
├─ assistant routing                       Product-owned intent and authority selection
├─ V3 remote MCP client declaration        Product-owned client policy
├─ delegated identity binding              Product-owned authenticated context
└─ provider contract + deterministic fixture
                                           Contract evidence only

External connector deployment
├─ Groupware MCP server process
├─ vendor/API-specific adapter
├─ private network access
├─ OAuth/service-account/token refresh
├─ organization endpoint and credentials
└─ operational scaling/health ownership
```

## Why the Sub-agent is internal

Routing, allowed capabilities, final output type and the permanent read-only rule are Product safety obligations. Moving the default Sub-agent outside the Product would let a tenant configuration silently change those invariants.

Tenant-specific vocabulary and optional policy overlays may later live in a signed Configuration Pack, but they must not replace the Product-owned base definition or widen authority.

## Why the actual MCP provider is external

A Groupware connector owns vendor dependencies, private network access, organization credentials, token refresh and operational lifecycle. Bundling those concerns into the Agent Runtime would couple the generic execution plane to every enterprise system and enlarge the credential blast radius.

## Internal exceptions

A local MCP server may stay inside the Runtime only when it is a Product-owned utility with no organization credential/network boundary, such as the immutable `reference-catalog`. Deterministic Groupware fixtures may also stay internal, but they must be marked as contract fixtures and must never be reported as a production provider.

## Future write path

`groupware-read-agent` and `groupware-read` remain permanently read-only. Future mutations use a separate boundary:

```text
groupware-action-agent
→ groupware-action MCP
→ separate credential reference
→ explicit approval and idempotency policy
→ audited mutation receipt
```

Write Tools are never appended to the read Agent or read MCP declaration.
