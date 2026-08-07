# agent-desktop

Planned desktop client for the multi-user OKCanvas Agent Runtime.

The desktop application is a service client, not an embedded Runtime. It must use the same
`/v1/service/**` contracts as `agent-web` and `agent-cli`, including tenant/principal ownership,
reconnectable persisted SSE, attachment upload, approval inbox, and Artifact retrieval.
