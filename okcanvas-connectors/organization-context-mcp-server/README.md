# OKCanvas Organization Context MCP Server

```text
Step: CONNECTOR_ORGANIZATION_CONTEXT_STEP003_RELATION_COMPLETENESS_EVIDENCE
Version: 0.3.0
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

`get_organization_entity` returns one stable entity, normalized relationships, and explicit completeness metadata: total relation count, returned count and a truncation flag. Missing or inconsistent completeness evidence fails closed before the response is exposed as MCP Tool evidence.

The Connector has no create/update/delete MCP Tool. The optional Example under `okcanvas-connector-examples/organization-context` is a construction guide, not a production dependency.
