# STEP085 Code Audit — Multi-MCP and Delegated Identity Foundation

## Audited parent

STEP084 had a versioned local Organization Context but Remote MCP V2 allowed exactly one exact HTTPS server with one bearer environment variable. It had no delegated user identity, tenant endpoint binding or multi-server runtime.

## Code-confirmed changes

### Definition and access policy

```text
okcanvas_agent_runtime/agent/mcp/definitions/models.py
okcanvas_agent_runtime/agent/mcp/definitions/catalog.py
okcanvas_agent_runtime/application/mcp_access/models.py
okcanvas_agent_runtime/application/mcp_access/catalog.py
okcanvas_agent_runtime/application/mcp_access/service.py
specs/mcp/access/access-policy.json
specs/mcp/access/credential-references.json
```

V3 is read-only, tenant-template, role-gated and credential-reference based. V2 remains unchanged and a V3 Agent may bind at most four remote servers.

### Identity and persistence

Authenticated Service ownership supplies tenant, principal and roles. A deterministic delegated identity is encrypted inside protected payload V6 and restored during confirm/execution. Admin or unauthenticated requests cannot manufacture delegated authority.

### Runtime adapter

The OpenAI MCP factory receives bound endpoints and identity headers, resolves bearer values only at execution time, connects multiple servers in parallel and records passive server-local circuit state. Public definitions, bindings, events and artifacts never contain secret values.

### Retained boundaries

GenericAgentExecutionService remains the sole Product execution plane. MCP writes, external endpoints, OAuth refresh, enterprise writes, automation, Tool Search and programmatic Tool calling remain disabled.

## Architecture effect

```text
RuntimeInfo fields: 877
Canonical modules: 336
Admin routes: 54
Service routes: 39
Other routes: 5
Total HTTP routes: 98
Compatibility aliases: 301
```

## Recorded corrections

OR-ISSUE-075 through OR-ISSUE-082 retain the exact V6 AAD, preparation signature, non-MCP gateway, V3 endpoint, stale current-state and local-evidence exclusion failures with recurrence gates.
