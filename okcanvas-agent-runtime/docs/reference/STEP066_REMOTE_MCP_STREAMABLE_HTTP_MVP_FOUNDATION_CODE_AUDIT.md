# STEP066 Code Audit — Remote MCP Streamable HTTP MVP Foundation

## Confirmed predecessor state

- STEP064A is the latest reported Windows-live accepted baseline.
- STEP065 source is present and deterministically validated, but no Windows result was reported.
- The explicit 2026-08-01 user direction moves operations stability after MVP.

## Existing product path

`AgentDefinition.mcp_servers` is resolved by `MCPServerCatalog`, bound by
`AgentRuntimeBindingCatalog`, constructed by `create_openai_mcp_runtime`, and passed to the SDK
Agent through `OpenAIGenericAgentGateway`. Existing hooks already reject undeclared server/tool
origins and write metadata-only Tool lifecycle Events.

The old catalog accepted only `okcanvas-mcp-server-v1` / `builtin-stdio` and required a
product-owned Python module. The old factory constructed only `MCPServerStdio`.

## Upstream findings

SDK 0.19.0 provides `MCPServerStreamableHttp` with URL, headers, HTTP timeout, SSE timeout,
termination and custom HTTP-client factory parameters. The SDK default client disables redirects,
but it does not disable environment proxy inheritance. `MCPServerManager` can run strict and
sequential, which matches the current closed single-server product path.

## Product implementation

- catalog schema v2 for remote definitions;
- HTTPS-only URL parsing with no userinfo/query/fragment;
- exactly one remote server and no stdio mixing;
- cache required and retries fixed to zero;
- optional external bearer environment value;
- strict HTTP client with `follow_redirects=False`, `trust_env=False`;
- static Tool filter and approval `never`;
- bounded remote result delegate;
- remote endpoint, auth mode/env name and factory SHA in Runtime binding;
- dedicated execution path `remote-mcp-streamable-http-execution-v1`;
- remote Session composition rejected.

## Security and evidence

The bearer value is read only while building the SDK server. It is absent from server definitions,
public catalog output, Runtime bindings, Events, Artifacts and evidence. The environment-variable
name is not secret and is bound. No external network or OpenAI call is part of deterministic
acceptance.

## Scope review

No STEP065 runtime was removed or modified for this feature. No health loop, reconnect manager,
write Tool, approval path, OAuth lifecycle, multi-server graph or hosted MCP capability was added.
