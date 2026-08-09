# OKCanvas Groupware MCP Server

`CONNECTOR_STEP002_STABLE_ORGANIZATION_CONTEXT_REFERENCE_FILTER` / `0.2.0`

This is the external read-only Groupware MCP Connector used by OKCanvas Agent Runtime. It does not contain a fake mode.

Implemented Tools:

- `search_notices`
- `search_mail`
- `list_calendar_events`

STEP002 adds an optional exact `context_ref` to all three Tool contracts:

```json
{"entity_type":"EMPLOYEE","entity_id":"employee-0017"}
```

The reference is an additional content filter. Existing tenant/principal/role visibility remains authoritative and the reference never grants access or impersonates an Organization employee.

The Connector validates the Runtime bearer and delegated identity, calls the configured Groupware REST/API, and echoes the validated applied `context_ref` in its Tool result so Runtime can verify evidence end-to-end.

## Environment

```text
OKCANVAS_CONNECTOR_MCP_BEARER=<runtime-to-connector bearer>
GROUPWARE_BASE_URL=https://groupware.company.com
GROUPWARE_API_BEARER=<connector-to-groupware bearer>
```

Local Example use may enable insecure HTTP and point at `okcanvas-connector-examples/groupware/groupware-api-fake`.

## Boundary

Read-only only. No Groupware write Tool, Agent routing, final-output authority, approval policy or stable-ID name fallback lives here.

## Validation state

STEP002 source is implemented but current executable acceptance remains deferred by the workspace test hold. Historical STEP001R1 evidence remains historical only.
