# Organization Context API Reference HANDOFF

```text
Step: EXAMPLE_ORGANIZATION_CONTEXT_STEP003_RELATION_COMPLETENESS_EVIDENCE
Version: 0.3.0
State: IMPLEMENTED_TEST_EXECUTION_DEFERRED_BY_USER
Status: EXAMPLE_TEMPLATE_ONLY
Production SOT: DATABASE
Example SOT: COMMITTED_JSON_FIXTURES
```

`tenant-a` retains 13 departments, 12 positions, 48 employees, 120 products, 120 clients, 80 glossary terms, 24 projects, 10 systems, 30 capabilities and 893 relations.

STEP003 preserves the STEP002R2 scalar/relation consistency closure and strengthens detailed entity GET responses with explicit relationship completeness evidence:

```text
relation_count
relations_returned_count
relations_truncated
```

The Example bounds detailed relationship rows to 100 but exposes the total count and truncation state so Runtime STEP093 never has to guess whether relationship evidence is complete.

The Example remains a construction guide, not an MCP server and not a production datastore. Current tests are source-prepared but not executed because the Workspace test hold remains active until MinIO is prepared.
