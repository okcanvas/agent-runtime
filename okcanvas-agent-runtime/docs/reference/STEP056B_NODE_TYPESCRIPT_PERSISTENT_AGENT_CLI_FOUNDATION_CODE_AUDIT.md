# STEP056B Code Audit — Node.js/TypeScript Persistent Agent CLI Foundation

## Inputs inspected

- STEP056 corrected ZIP and current `AGENTS.md`, `HANDOFF.md`, `PLANS.md`, Roadmap and Validation;
- Python smoke client under `src/okcanvas_agent_runtime/tui_client`;
- Windows launchers and local environment loader;
- Control API Agent catalog, preflight, confirmation, Run, Invocation, Artifact, Evaluation and
  persisted SSE endpoints;
- Product Run submission and protected-payload retention contracts;
- current package inclusion policy and Windows launcher acceptance.

## Findings

### 1. STEP056 was not a persistent client

`TUIApplication.run_interactive()` selected one Agent and one Evaluation case, read one multiline
request, asked for a model, required the user to type the exact challenge, rendered all Events and raw
JSON, evaluated the Run, and returned. `sh_tui.cmd` then exited.

### 2. A Node client needs no Runtime internals

The existing REST/SSE surface already supports the required first product loop:

- `GET /healthz`;
- `GET /v1/agent-definitions`;
- `POST /v1/run-submissions/preflight`;
- `POST /v1/run-submissions/{id}/confirm`;
- `GET /v1/runs/{id}/events/stream`;
- `GET /v1/runs/{id}`;
- `GET /v1/runs/{id}/invocations`;
- `GET /v1/runs/{id}/artifact`;
- optional `POST /v1/runs/{id}/evaluations`.

No Python Runtime import, SQLite access, Artifact path access, protected-payload access, Tool/MCP
execution, or `/reference` execution is necessary.

### 3. Evaluation is optional in the API

The previous client made Evaluation mandatory by its own flow. The Runtime does not require it for a
successful Run. STEP056B leaves Evaluation off by default and invokes it only when an explicit
`--evaluation-case-id` is supplied.

### 4. Exact confirmation can remain governed without exposing the challenge

The client receives the immutable challenge from preflight and sends that exact value only after the
user accepts the simple local prompt. The challenge is not shown, copied, modified, or recomputed.
The Control API remains the final confirmation authority.

### 5. Installability begins with package shape, not immediate publication

`clients/okcanvas-agent-cli/package.json` defines a future npm `bin`. Compiled `dist/` is included in
the source ZIP, so target execution does not require TypeScript. There are zero runtime npm
dependencies. Current development validation uses the available TypeScript compiler; registry
publication is deferred.

### 6. Environment templates were ambiguous

The root exposed `.env.example`, `.env.local.example`, and `.env.local.cmd.example`. STEP056B retains
only `.env.local.example` as the canonical source. `sh_init_local_env.cmd` creates `.env.local` and
generates distinct local authorities plus a valid 32-byte protected-payload key without printing
those values.

### 7. Windows launcher policy needed an explicit Node client exception

All Python Runtime launchers still use `.venv\\Scripts\\python.exe`. `sh_tui.cmd` is deliberately the
single direct Node launcher and must contain no Python path. STEP030A and its regression test now
express that exact split rather than forcing a Node product client through Python.

## Implemented files

```text
clients/okcanvas-agent-cli/
├─ package.json
├─ package-lock.json
├─ tsconfig.json
├─ README.md
├─ src/
│  ├─ api-client.ts
│  ├─ app.ts
│  ├─ cli.ts
│  ├─ config.ts
│  ├─ node-shims.d.ts
│  ├─ render.ts
│  ├─ sse.ts
│  └─ types.ts
├─ dist/
└─ test/
```

Additional product files:

- `sh_tui.cmd` — direct Node launcher;
- `sh_init_local_env.cmd` and `scripts/init_local_env.py`;
- `scripts/run_step056b_acceptance.py`;
- `sh_run_step056b_acceptance.cmd`;
- baseline, package, launcher and static regression tests.

## Security boundary

- credentials are read from `.env.local` or inherited environment only;
- only an explicit loopback URL with an explicit port is accepted;
- raw credentials are never printed;
- exact challenge is sent only to the local confirmation endpoint and is not displayed;
- request text enters the existing protected-payload boundary;
- the Node CLI has no direct access to Runtime databases, keys, Agent SDK or execution modules.
