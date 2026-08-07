# WORKSPACE ISSUE 029 — Organization Context resolve exceeded MCP result budget

## Actual Windows evidence

The STEP007 Live OpenAI run reached the actual Runtime, stateless child Agent, Organization Context MCP Connector and Node Example, but the first turn failed immediately after `resolve_organization_context` started.

The same STEP007 source and committed fixtures reproduced the exact contract failure:

```text
exact employee resolve response: 34,994 characters
Runtime MCP result budget:        32,000 characters
same-name ambiguity response:     12,977 characters
```

The resolver returned all ranked candidates with full records and relationships. The exact employee query had thirteen candidates, so a valid product response exceeded the Runtime boundary.

## Closure

STEP007R1 does not raise the Runtime limit. It changes the product response contract:

```text
resolve → top-score candidates with details
search  → at most 20 compact summaries
get     → one entity with full details and relationships
```

The Runtime now emits a redacted `okcanvas-mcp-tool-failed-v1` diagnostic when a remote MCP result exceeds its bound. It retains server ID, tool name, observed characters and maximum characters, but never persists raw arguments, raw results, bearer values or raw errors.
