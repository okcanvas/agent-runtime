# Connector mapping guide

The real Connector maps MCP read tools to these product APIs. Customer implementations can use any
storage engine, but must preserve the response schemas, delegated identity headers, ambiguity
semantics, catalog revision, change feed ordering, and tombstone behavior.
