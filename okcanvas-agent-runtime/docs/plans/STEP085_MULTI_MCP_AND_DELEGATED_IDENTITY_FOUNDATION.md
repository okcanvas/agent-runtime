# STEP085 — Multi-MCP and Delegated Identity Foundation

## Identity

```text
STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION
version 2.65.0
parent STEP084 / 2.64.0 Windows deterministic accepted
rollback STEP081D / 2.61.4 Windows live 80/80
```

## Objective

Extend the historical single read-only Remote MCP contract without weakening it. STEP085 adds a V3-only path for up to four read-only remote MCP servers bound to authenticated tenant/principal/roles and credential references. It does not configure real enterprise endpoints or enable writes.

## Implemented

- V2 exact-URL/single-server Remote MCP compatibility retained;
- V3 tenant-template endpoint definitions;
- maximum four remote servers and no local/remote transport mixing;
- delegated identity from authenticated Service principal context;
- role checks and deterministic delegation fingerprint;
- credential references resolved to environment variables without persisting secret values;
- protected payload V6 identity persistence and exact restoration;
- delegated tenant/principal/delegation headers;
- passive process-local circuit breaker state;
- parallel connection manager for multiple remote servers;
- Service capability projection for policy, counts and disabled write state.

## Fail-closed defaults

The shipped Product Configuration Pack contains zero delegated credential references and no V3 enterprise servers. Missing identity, role, credential reference, unsafe tenant, excessive server count, circuit-open state or malformed endpoint blocks execution.

## Not implemented

- real ERP/ESS/Groupware endpoints;
- OAuth authorization-code flow or token refresh;
- write-capable MCP Tools;
- active health probes or distributed circuit state;
- Tool Search/programmatic Tool calling;
- durable automation.

## Validation

Multi-MCP/identity validator, Architecture, retained STEP084 context, retained execution/distribution, integrated acceptance, portability, full source/Fresh regression, installation and Constitution Compliance.

## Next selected step

```text
STEP086_GROUPWARE_READ_ONLY_VERTICAL
```
