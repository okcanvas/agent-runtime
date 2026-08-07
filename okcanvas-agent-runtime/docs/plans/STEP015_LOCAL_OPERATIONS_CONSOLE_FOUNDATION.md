# STEP015 — Local Operations Console Foundation

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Goal

Expose the already stable product state and catalogs through one local-admin, read-only operating surface without introducing a second backend, frontend state store, write workflow, or deployment control.

## Reference inspection

Inspected before implementation:

- `reference/upstream/openai-cs-agents-demo/ui/app/page.tsx`
- `reference/upstream/openai-cs-agents-demo/ui/components/agent-panel.tsx`
- `reference/upstream/openai-cs-agents-demo/ui/components/runner-output.tsx`
- `reference/upstream/openai-cs-agents-demo/ui/lib/api.ts`
- `reference/upstream/openai-cs-agents-demo/python-backend/main.py`
- `reference/upstream/openai-agents-streaming-api/src/api/main.py`

## Decisions

### ADAPT

- separate overview, Agent, Run/Event, and guardrail/evidence-oriented panels;
- keep frontend API access in one small adapter;
- use the existing FastAPI origin rather than permissive cross-origin configuration;
- show canonical product Events rather than SDK stream classes.

### REJECT

- importing or running any `/reference` UI code;
- ChatKit/Next.js as a product dependency for this foundation;
- wildcard CORS;
- instruction, prompt, local path, API key, or raw model output disclosure;
- mutation controls.

### DEFER

- Vue or another compiled frontend framework;
- persisted SSE consumption in the browser;
- tenant/organization authorization;
- remote operations deployment.

## Product contract

- `/console` serves only the shell and product-owned static assets.
- `/v1/**` remains protected by `X-OKCanvas-Admin-Key`.
- the browser key is stored only in per-tab `sessionStorage`.
- console JavaScript issues authenticated GET requests only.
- summary/reference refresh never mutates Product or Evaluation SQLite state.
- reference integrity is verified using the project-owned Reference Catalog.

## New endpoints

- `GET /v1/operations/summary`
- `GET /v1/tasks?status=&limit=&offset=`
- `GET /v1/runs?status=&agent_definition_id=&limit=&offset=`

## Console sections

- overview and status distribution;
- recent and filtered Runs;
- canonical Event drill-down;
- Agent and MCP definitions;
- Evaluation Cases, Suites, and recent history;
- immutable Reference integrity.

## Non-scope

- create/cancel Run;
- create Evaluation or Baseline;
- approval decisions;
- Codex commands;
- MCP writes;
- deployment, promotion, rollback;
- raw Artifact download;
- instructions or prompt display.

## Acceptance

`sh_run_step015_acceptance.cmd` checks shell/assets, CSP, key handling, GET-only browser code, authentication, product counts, catalogs, MCP read-only state, Reference 4/4 integrity, and unchanged Product/Evaluation DB hashes after GET operations.
