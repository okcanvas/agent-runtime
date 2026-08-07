# OKCanvas Organization Context MCP Server

```text
Step: CONNECTOR_ORGANIZATION_CONTEXT_STEP002R1_RUNTIME_WIRING_CONTRACT_ALIGNMENT
Version: 0.2.1
Production: true
Read-only: true
Production SOT: external Organization Context database
```

The Connector owns no organization data and has no fake mode. It translates delegated, read-only MCP calls into an external Organization Context REST API.

## MCP Tools

```text
resolve_organization_context
search_organization_context
get_organization_entity
resolve_organization_terms
search_organization_terms
get_organization_term
get_organization_catalog_state
get_organization_changes
```

The first three Tools support unified entities and relationships. The retained five Tools preserve the STEP001 Glossary contract. No create/update/delete MCP Tool exists; external product administration remains outside the Agent boundary.

The optional Example is located at `okcanvas-connector-examples/organization-context/organization-context-api-fake`. It is a construction guide, not a Connector dependency.
