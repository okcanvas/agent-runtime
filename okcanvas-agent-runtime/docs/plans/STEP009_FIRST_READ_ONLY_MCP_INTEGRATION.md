# STEP009 — First read-only MCP integration

## Purpose

Expose the accepted STEP006 Reference Catalog through one allowlisted local stdio MCP server and
connect it to one generic Agent. Preserve product Task/Run/Event/Artifact state and never make
`/reference` an executable dependency.

## Reference inspection

### ADOPT

- `reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/server.py`
  - `MCPServerStdio` transport, client-session timeout, retry settings, Tool filtering and cleanup.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/manager.py`
  - same-task connect/cleanup lifecycle, strict connection failure and bounded timeouts.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/util.py`
  - static Tool allowlist through `create_static_tool_filter`.
- `reference/upstream/openai-agents-python-0.19.0/examples/mcp/tool_filter_example/main.py`
  - Agent `mcp_servers` connection and explicit static allowlist.

### ADAPT

- `reference/upstream/openai-agents-python-0.19.0/examples/mcp/streamablehttp_example/server.py`
  - `FastMCP` Tool declaration only; transport is changed to local stdio.
- `reference/upstream/openai-agents-python-0.19.0/tests/mcp/test_runner_calls_mcp.py`
  - deterministic fake-server contract testing and Tool-call verification.
- `reference/upstream/openai-agents-python-0.19.0/tests/mcp/test_tool_filtering.py`
  - allowlist-first testing pattern.

### REJECT / DEFER

- generic filesystem MCP servers: rejected because their write surface is broader than required;
- SSE and Streamable HTTP: deferred until a remote server is justified;
- ERP, ESS and PlanVM MCP: deferred;
- writable Tools and arbitrary server commands: rejected;
- Tool arguments and result content in product Event payloads: rejected;
- direct imports from `/reference`: prohibited.

## Product contract

Server allowlist:

```text
reference-catalog
  search_reference
  read_reference_file
```

Limits:

- search results: maximum 8;
- read range: maximum 80 lines;
- serialized result: maximum 24,000 characters;
- connect timeout: 10 seconds;
- Tool timeout: 8 seconds;
- retry: one bounded retry;
- approval: never, because both Tools are read-only and server identity is allowlisted.

Canonical Event payloads retain only server ID, Tool name and presence flags. They do not retain
arguments, query text, source text, Tool output, Tool call ID, API key or Agent instructions.

## Acceptance

Deterministic acceptance requires:

- strict server and Tool allowlists;
- bounded search and read;
- `src/agents/run_state.py` discovery;
- MCP-sourced `tool.started` and `tool.completed` Events;
- no raw request, key or reference content in SQLite;
- all four Reference tree hashes unchanged.

Live acceptance additionally requires actual stdio protocol connection, both Tool calls through the
installed MCP SDK, and a real Agent Run that records both Tool start/completion pairs.
