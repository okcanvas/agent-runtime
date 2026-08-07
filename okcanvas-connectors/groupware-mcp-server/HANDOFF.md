# Groupware MCP Server HANDOFF

## Current baseline

```text
Step: CONNECTOR_STEP001R1_ASYNC_TEST_RUNNER_DEPENDENCY_CLOSURE
Version: 0.1.1
State: LOCAL_DETERMINISTIC_ACCEPTED
Project: okcanvas-connectors/groupware-mcp-server
Parent: CONNECTOR_STEP001_GROUPWARE_READ_MCP_FOUNDATION / 0.1.0
```

## Contract lineage

The authoritative client-side parent is `okcanvas-agent-runtime` STEP086R2 / 2.66.2. Its exact
`okcanvas-groupware-read-provider-contract-v2` is retained at
`contracts/runtime-provider-contract.json`. Connector-only HTTP authentication and role policy live
separately in `contracts/connector-binding-contract.json`.

Inbound requirements:

```text
Authorization
X-OKCanvas-Tenant-ID
X-OKCanvas-Principal-ID
X-OKCanvas-Roles
X-OKCanvas-Delegation-ID
required role: agent-user
```

The Connector recomputes the delegation fingerprint, binds the tenant path, rejects identity/role
mismatch and never receives `credential_ref`.

## STEP001R1 correction

STEP001 async tests used `pytest.mark.asyncio` while the documented clean-environment installation
installed only the project and `pytest`. A developer machine with an incidental `pytest-asyncio`
installation passed, but a fresh Windows virtual environment failed three tests. STEP001R1 removes
that hidden dependency: sync pytest functions execute the real async scenarios through
standard-library `asyncio.run()`. A static recurrence gate rejects `pytest.mark.asyncio` and
`pytest_asyncio` in Connector tests.

## Implemented

- stateless Streamable HTTP JSON-RPC endpoint at `POST /tenants/{tenant_id}/mcp`;
- `initialize`, `ping`, `tools/list`, `tools/call` and initialized notification handling;
- exact read Tools: `search_notices`, `search_mail`, `list_calendar_events`;
- configurable `HttpGroupwareClient` with no fake mode;
- tenant/principal/roles/delegation/request-id forwarding to Groupware REST/API;
- bounded timeout/retry with default retry count zero;
- stable secret-free downstream error conversion;
- local optional-example integration through the actual Connector code.

## Not implemented or verified

- vendor-specific Groupware API profile beyond the Connector V1 HTTP contract;
- vendor OAuth/token refresh or private-network credentials;
- write Tools or `groupware-action` MCP;
- production TLS termination, scaling or durable state;
- live verification against an actual company Groupware product.

## Validation

```text
Python tests: 10/10 PASS
Connector acceptance: 7/7 PASS
Optional API-example integration: 7/7 PASS
```

The optional example is not a production dependency and is not imported by Connector source.

## Issues

```text
CONNECTOR-ISSUE-001 delegated roles were declared by Runtime but not transmitted before STEP086R2
CONNECTOR-ISSUE-002 async pytest plugin was an undeclared clean-environment dependency
```

## Run

```bash
python -m groupware_mcp_server
```

Required environment is documented in `README.md`.
