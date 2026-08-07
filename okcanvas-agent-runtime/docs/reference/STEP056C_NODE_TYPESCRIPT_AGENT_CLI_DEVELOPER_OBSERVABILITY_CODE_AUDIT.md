# STEP056C Code Audit — Node.js/TypeScript Agent CLI Developer Observability

## Inputs inspected

- packaged STEP056B Node.js/TypeScript CLI source, compiled `dist/`, tests and deterministic acceptance;
- the user-reported Windows transcript from real `sh_tui` use;
- the previous Python STEP056 smoke output;
- Control API health, Agent catalog, governed preflight/confirmation, persisted SSE, Run, Invocation,
  Artifact and recorded Evaluation endpoints;
- local environment, launcher and package inclusion contracts.

## Findings

### 1. Persistent product flow is correct, but development evidence was missing

STEP056B fixed the single-run problem. The default answer-first transcript is usable, but developers
need to inspect the exact governed path without returning to the Python smoke.

### 2. Observability can be implemented entirely in the Node client

The Control API already returns all required evidence. The Node client only needs bounded callbacks at
three points: preflight received, confirmation completed and each persisted SSE Event received. No new
Runtime endpoint or direct Product store access is required.

### 3. Exact challenge visibility and exact challenge copying are different concerns

The challenge is useful diagnostic evidence in explicit debug mode. The user must still never copy it
back manually. The CLI receives the immutable value, asks only `Y/n`, and transmits the exact value to
the existing confirmation endpoint.

### 4. Evaluation remains optional

Debug mode reports `NOT RUN` unless an Evaluation was explicitly requested. `/evaluate <case-id>` uses
`POST /v1/runs/{run_id}/evaluations` for the last Run and updates the local last-outcome state.

### 5. Catalog-first implicit Agent selection was incorrect

STEP056B selected the first compatible Agent when no `--agent-id` was supplied. A real catalog may put
a specialist first. STEP056C uses explicit precedence:

1. `--agent-id`;
2. `OKCANVAS_DEFAULT_AGENT_ID`;
3. the only compatible Agent;
4. otherwise an interactive numbered/ID selection.

Script mode with multiple Agents requires an explicit Agent ID.

## Implemented changes

- `src/types.ts`: execution observer and debug option contracts;
- `src/api-client.ts`: preflight/confirmation/Event observers and reusable post-Run Evaluation method;
- `src/render.ts`: bounded preflight/Event/Run/Artifact/Evaluation diagnostic renderers;
- `src/app.ts`: `--debug`, `/debug`, `/status`, `/evaluate`, explicit initial Agent selection;
- `src/config.ts`: debug argument and `OKCANVAS_DEFAULT_AGENT_ID`;
- package version `0.2.0`, rebuilt retained `dist/` and expanded Node tests;
- `scripts/run_step056c_acceptance.py` and Windows launcher.

## Security boundary

- debug output may contain Product IDs, Runtime binding SHA and the exact local confirmation challenge;
- debug output never contains administrator key, submitter key, API key or protected payload content;
- debug is off by default;
- remote Control API URLs remain forbidden;
- the challenge is never retyped or recomputed;
- Node still has no direct Runtime, SQLite, Agent SDK, Tool/MCP or `/reference` execution access.
