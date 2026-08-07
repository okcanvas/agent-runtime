# OKCanvas Connectors

Independent production Connector projects. Each owns its dependency graph, environment, contracts,
tests, and package. Connectors must not import Runtime or optional Connector Examples.

- `groupware-mcp-server`: read-only Groupware MCP Connector.
- `organization-context-mcp-server`: read-only Organization Context MCP Connector; external mutable
  product administration is intentionally not exposed as MCP mutation Tools.
