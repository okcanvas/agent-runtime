# Remote Streamable HTTP MCP V1

This contract is an MVP capability boundary, not an operations-management subsystem.

A remote server definition uses schema `okcanvas-mcp-server-v2` and kind
`remote-streamable-http`. It is enabled only after its exact `server_id` is added to
`specs/mcp/allowlist.json` and an Agent definition names that server.

V1 invariants:

- exactly one remote MCP server per Agent;
- no local-stdio/remote transport mixing;
- exact immutable HTTPS URL with an explicit path;
- no URL userinfo, query, fragment, redirect following, or proxy-environment inheritance;
- static read-only Tool allowlist;
- cached Tool list for one execution;
- zero MCP retry attempts;
- approval mode `never` because write Tools are forbidden;
- optional bearer token read only from the named environment variable;
- bearer value never enters definitions, public catalog output, Runtime binding, Events, Artifacts, or evidence;
- bounded Tool output before it is returned to the Agent SDK;
- strict single-server connection through the installed SDK `MCPServerStreamableHttp` and
  `MCPServerManager`.

V1 does not include SSE, Hosted MCP, OAuth refresh, arbitrary headers, multiple remote servers,
health dashboards, reconnect loops, prompts/resources, write Tools, MCP approval, Session
composition, or background lifecycle management.

`specs/mcp/examples/remote-streamable-http.server.json` is a non-enabled template. The reserved
`.invalid` endpoint must be replaced by an actual organization endpoint before copying the file
under `specs/mcp/servers/<server-id>/server.json` and updating the allowlist.
