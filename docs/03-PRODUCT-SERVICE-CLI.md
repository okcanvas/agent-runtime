# Product Service CLI

The independent `okcanvas-agent-cli` project remains at CLI STEP001R1 / 0.2.1 and uses only External Bearer plus `/v1/service/**`.

```text
Prompt 1: Groupware read request
→ automatic Main Assistant route
→ Runtime confirmation/preflight
→ one stateless Groupware child call
→ persisted SSE
→ grounded final Artifact

Prompt 2: general continuation
→ same Runtime-owned Main Assistant Session
→ zero Groupware child calls
→ persisted SSE and final Artifact
```

The CLI does not access Runtime SQLite, Runtime source, Connector source, administrator routes, or administrator headers. Session history, delegated identity derivation and execution state remain Runtime-owned. The CLI bearer is masked from acceptance command evidence.
