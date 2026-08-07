# OKCanvas Agent Service CLI

Current baseline: `CLI_STEP001R1_WINDOWS_NODE_TEST_RUNNER_PATH_SPACE_CLOSURE` / `0.2.1`.
State: `PRODUCT_READY`.

The CLI is an independent Product client. It uses only the authenticated Service API:

```text
External Bearer
→ /v1/service/assistant/sessions
→ /v1/service/assistant/run-submissions/preflight
→ /v1/service/run-submissions/{submission_id}/confirm
→ /v1/service/runs/{run_id}/events/stream
→ /v1/service/runs/{run_id}/outcome and artifacts
```

It does not import Runtime or Connector source and does not use administrator headers or administrator routes.

## Run

```cmd
set OKCANVAS_SERVICE_BASE_URL=http://127.0.0.1:8765
set OKCANVAS_SERVICE_BEARER=<service-user-token>
sh_run_cli.cmd
```

Useful options:

```text
--yes
--model <id>
--session-id <id>
--script <utf8-file>
--no-session
--debug
```

The default flow creates an Assistant Session and reuses it for consecutive prompts. The Runtime owns routing, execution, persistence, and MCP delegation. The CLI owns only user interaction and Service HTTP/SSE transport.

## Windows acceptance runner

The acceptance runner enumerates test files in Node and invokes `process.execPath` with `shell: false`. This keeps Node installations under paths such as `C:\Program Files\nodejs\node.exe` safe.
