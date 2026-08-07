# MCP Servers

Each enabled directory contains one immutable `server.json` and must also be named in
`../allowlist.json`.

Supported definitions:

- `okcanvas-mcp-server-v1`, kind `builtin-stdio`;
- `okcanvas-mcp-server-v2`, kind `remote-streamable-http`, one exact read-only endpoint;
- `okcanvas-mcp-server-v3`, kind `remote-streamable-http`, tenant-template delegated identity and
  up to four read-only servers.

Remote servers are client-only. The Runtime does not package or start the organization-owned MCP
server. The committed Groupware V3 endpoint uses `.invalid` and therefore fails closed until an
operator supplies a real HTTPS endpoint and environment-backed credential value.
