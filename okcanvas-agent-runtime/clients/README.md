# Client workspaces

The STEP081 repository owns all JavaScript client workspaces below `clients/`.

- `clients/cli/` is the current development and acceptance-test CLI harness.
- `clients/web/` is the planned browser service client.
- `clients/desktop/` is the planned desktop service client.
- `clients/dev-cli/` contains development-only CLI support.

No client embeds Runtime implementation modules. Product clients consume `/v1/service/**` APIs and persisted SSE. The current CLI harness may still exercise explicitly development-only administrator surfaces until a later STEP promotes or replaces it.
