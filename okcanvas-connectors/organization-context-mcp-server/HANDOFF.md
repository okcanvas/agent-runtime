# Organization Context MCP Connector HANDOFF

```text
Step: CONNECTOR_ORGANIZATION_CONTEXT_STEP003_RELATION_COMPLETENESS_EVIDENCE
Version: 0.3.0
State: IMPLEMENTED_TEST_EXECUTION_DEFERRED_BY_USER
Read-only Tools: 8
Fake mode: absent
Production SOT: DATABASE through external product API
```

STEP003 strengthens `get_organization_entity`: every returned entity must expose relationship completeness metadata (`relation_count`, `relations_returned_count`, `relations_truncated`). The Connector rejects missing or inconsistent metadata with safe error code `ORGANIZATION_CONTEXT_RELATION_COMPLETENESS_INVALID` before returning Tool evidence to the Runtime.

This is required by Runtime STEP093 relation-aware follow-up so a truncated relationship page can never be mistaken for the complete relation set.

The Connector remains read-only, owns no organization data and keeps the same eight MCP Tools. Tests are source-prepared but not executed because the Workspace test hold remains active until MinIO is prepared.
