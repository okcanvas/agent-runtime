# Groupware Read-only Sub-agent

This Product-owned declarative Sub-agent is stored inside the Runtime because routing, output
safety, and capability binding are Product responsibilities. It uses the generic Agent execution
plane and one V3 remote MCP client declaration.

The actual organization Groupware MCP provider is not implemented in this Runtime. It must be a
separately deployed external connector service near the protected Groupware network and credential
boundary. Deterministic fixtures under `fixtures/groupware/read-provider-contract` validate the
provider contract only; they are not a production MCP server.

This Sub-agent remains permanently read-only. Future mutation capability must use a separate
`groupware-action-agent`, separate `groupware-action` MCP server, and separate credential/approval
boundary.
