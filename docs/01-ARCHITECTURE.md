# Workspace Architecture

## STEP003 execution path

```text
Product Service CLI
  → Agent Runtime Service API / persisted SSE
  → organization-assistant-session-agent (durable root SQLite Session)
  → groupware-read-agent (stateless Agent-as-Tool, maximum one call)
  → groupware-read MCP client (child-owned)
  → Groupware MCP Connector (external process)
  → Groupware REST/API
```

Development and deterministic acceptance replace only the final enterprise API with the independent Node `groupware-api-fake` Example. The Connector remains the actual MCP Server and contains no fake mode.

## Ownership invariants

- Runtime does not contain Connector or Example source.
- Root Main Assistant owns Session history; child Session is `NONE`.
- Root does not own the Groupware MCP binding.
- Delegated identity is scoped to the Groupware child turn.
- Groupware writes remain disabled.

## Environment isolation

- Runtime: `okcanvas-agent-runtime/.venv`
- Connector: `okcanvas-connectors/groupware-mcp-server/.venv`
- Product CLI: `okcanvas-agent-cli/node_modules`
- Example: `okcanvas-connector-examples/groupware/groupware-api-fake/node_modules`

The Workspace root must not contain `.venv` or `node_modules`.
