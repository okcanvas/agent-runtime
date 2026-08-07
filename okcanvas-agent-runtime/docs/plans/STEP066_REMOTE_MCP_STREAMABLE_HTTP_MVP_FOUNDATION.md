# STEP066 — Remote MCP Streamable HTTP MVP Foundation

## Baseline

- Version: `2.46.0`
- Current STEP: `STEP066_REMOTE_MCP_STREAMABLE_HTTP_MVP_FOUNDATION`
- Windows-live accepted predecessor: STEP064A / `2.44.1`
- Retained post-MVP hardening: STEP065 / `2.45.0`, deterministic only

## Why this STEP

The existing MCP path supports one product-owned local stdio server. That proves the SDK Tool
primitive but does not connect an Agent to an organization-owned document, issue, search or
business API service. Remote Streamable HTTP adds a user-visible integration capability and reuses
the existing governed execution, Tool-event redaction, Product ledger and Runtime binding.

Hosted Search and multimodal input require new source/retention/input contracts. Remote MCP is the
smallest next core capability because the Agent execution path already exists.

## Adopted upstream behavior

Inspected reference paths:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/server.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/manager.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/util.py`
- `reference/upstream/openai-agents-python-0.19.0/examples/mcp/streamable_http_remote_example/main.py`
- `reference/upstream/openai-agents-python-0.19.0/examples/mcp/manager_example/app.py`

Adopted:

- installed SDK `MCPServerStreamableHttp`;
- installed SDK `MCPServerManager` lifecycle;
- SDK static Tool filter;
- SDK transport parameters for URL, headers, HTTP timeout and SSE read timeout.

Adapted:

- product-owned exact definition catalog;
- strict HTTPS-only endpoint policy;
- bearer token read from one named environment variable;
- custom strict `httpx.AsyncClient` factory with redirects and proxy environment disabled;
- product-owned result-size wrapper before Tool output returns to the Agent SDK;
- immutable Runtime binding including transport and endpoint identity.

Deferred:

- multiple remote servers, reconnect, health management, SSE and Hosted MCP;
- OAuth refresh, arbitrary headers and certificate customization;
- prompts/resources, write Tools and MCP approval;
- remote MCP with SQLite Session.

## Exact contract

- definition schema: `okcanvas-mcp-server-v2`;
- kind: `remote-streamable-http`;
- exact absolute HTTPS URL with explicit path;
- no credentials, query or fragment in URL;
- exactly one remote server and no transport mixing;
- `read_only=true`;
- `cache_tools_list=true`;
- `max_retry_attempts=0`;
- `authorization_mode=none|bearer-env`;
- `require_approval=never`;
- `use_structured_content=false`;
- strict SDK manager with sequential connection;
- Tool result bounded by `max_result_chars` before return.

## Acceptance

The deterministic gate must prove the priority reset, exact catalog contract, secret isolation,
official SDK construction, static filtering, strict HTTP client, bounded result, Runtime binding,
Session exclusion, local stdio regressions, compileall, Node release integrity and unchanged
References. It performs no external network or model call.
