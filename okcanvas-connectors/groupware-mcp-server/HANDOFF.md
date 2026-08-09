# Groupware MCP Server HANDOFF

```text
Step: CONNECTOR_STEP002_STABLE_ORGANIZATION_CONTEXT_REFERENCE_FILTER
Version: 0.2.0
State: IMPLEMENTED_TEST_PENDING
Project: okcanvas-connectors/groupware-mcp-server
Parent: CONNECTOR_STEP001R1_ASYNC_TEST_RUNNER_DEPENDENCY_CLOSURE / 0.1.1
```

Provider contract: `okcanvas-groupware-read-provider-contract-v3`.

STEP002 adds optional strict `context_ref {entity_type, entity_id}` to the existing three read Tools and forwards it unchanged to Groupware REST/API. The Tool result echoes the applied validated reference. It remains stateless and read-only.

Authorization remains tenant/principal/roles/delegation based. `context_ref` is not authorization and must not broaden visibility.

Current executable Connector acceptance and optional Example integration are source-prepared but unexecuted under the workspace test hold.
