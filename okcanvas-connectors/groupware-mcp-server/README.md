# OKCanvas Groupware MCP Server

`CONNECTOR_STEP001R1_ASYNC_TEST_RUNNER_DEPENDENCY_CLOSURE` / `0.1.1`

This is the real external Connector product for the Runtime-owned `groupware-read-agent`.
It is not packaged as Runtime product code and it does not contain a fake mode.

```text
okcanvas-agent-runtime
  -> Streamable HTTP MCP
okcanvas-connectors/groupware-mcp-server
  -> Groupware REST/API
configured Groupware product
```

Implemented read Tools:

- `search_notices`
- `search_mail`
- `list_calendar_events`

The Connector authenticates the Runtime bearer, validates tenant/principal/roles/delegation,
recomputes the delegation fingerprint, requires `agent-user`, calls the configured Groupware API,
normalizes responses and maps downstream errors into secret-free MCP Tool errors.

## Required environment

```text
OKCANVAS_CONNECTOR_MCP_BEARER=<runtime-to-connector bearer>
GROUPWARE_BASE_URL=https://groupware.company.com
GROUPWARE_API_BEARER=<connector-to-groupware bearer>
```

Local example use may set `GROUPWARE_ALLOW_INSECURE_HTTP=1` and point `GROUPWARE_BASE_URL` at the
optional `okcanvas-connector-examples/groupware/groupware-api-fake` template.

## Setup and validation

Windows clean environment:

```cmd
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e . pytest
.venv\Scripts\python.exe scripts\run_acceptance.py
```

Canonical development-extra installation is also available:

```cmd
.venv\Scripts\python.exe -m pip install -e ".[test]"
```

The async HTTP scenarios use the Python standard-library `asyncio.run()` runner.
`pytest-asyncio` is not required for Connector acceptance.

## Run

```bash
python -m groupware_mcp_server
```

Default endpoint:

```text
POST /tenants/{tenant_id}/mcp
```

## Boundary

The connector does not own Agent instructions, routing, final-output contracts, approvals or
future write authority. Future writes require a separate `groupware-action-agent`, separate MCP
server and separate credential.
