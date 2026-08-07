# Workspace Constitution

1. Do not guess. Inspect actual code, contracts, tests, logs, and artifacts before deciding.
2. Runtime, Product CLI, Connectors, and Connector Examples are independent projects.
3. Each project owns its dependency graph, virtual environment or node_modules, tests, version, and package.
4. Cross-project Python or JavaScript source imports are forbidden.
5. Project interaction is allowed only through declared HTTP, SSE, MCP, and external-system API contracts.
6. The Connector Example is optional and must never become a production dependency or MCP replacement.
7. Every reproducible failure or near-miss must be recorded in `docs/issues` with a recurrence gate.
8. A packaged ZIP must contain enough documentation and evidence to continue in another conversation.
