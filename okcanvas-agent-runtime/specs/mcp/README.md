# MCP Definitions

This is a declarative specification area, not the third-party `mcp` Python package. It must not
contain `__init__.py`.

Two immutable read-only transports are supported:

- `okcanvas-mcp-server-v1` / `builtin-stdio`: product-owned local subprocess MCP;
- `okcanvas-mcp-server-v2` / `remote-streamable-http`: one exact allowlisted HTTPS MCP endpoint.

Server IDs are selected from `allowlist.json`; every enabled server has an immutable
`servers/<server-id>/server.json`; the Agents SDK applies a second static Tool allowlist. Write
Tools, dynamic endpoint selection, remote retries, redirects, proxy-environment inheritance, and
raw credential persistence are forbidden.

The built-in `reference-catalog` server remains local stdio. A non-enabled remote template is in
`examples/remote-streamable-http.server.json`. The exact V1 remote contract is documented in
`contracts/REMOTE_STREAMABLE_HTTP_V1.md`.

Executable implementation lives below `src/okcanvas_agent_runtime/`. `/reference` is consulted but
never directly imported.
