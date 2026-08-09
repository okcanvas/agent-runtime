# Organization Context Interpretation Hints MCP

Runtime-only, model-context enrichment profile for the same production Organization Context connector.
It is **not** attached to an Agent as an MCP Tool surface. The Runtime calls only bounded search Tools
with the unchanged user utterance, projects a minimal hint shape, and marks the result non-authoritative.
Stable entity IDs, full records, relation graphs, delegated identity and credentials are not exposed in
the model-facing hint projection.

Allowed Tools:

- `search_organization_context`
- `search_organization_terms`

The committed `.invalid` endpoint remains fail-closed. Live/test harnesses may bind the same connector
endpoint used by the execution profile without changing Connector Product behavior.
