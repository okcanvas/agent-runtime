# STEP056 — TUI Client Foundation

## Status

- Version: `2.36.0`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`
- Previous Windows baseline: STEP055 `WINDOWS_LIVE_ACCEPTED`

## Purpose

Turn the accepted Agent Runtime into a directly usable local product surface before adding more
Sub Agents, Tools, or Sandbox capability. STEP056 introduces one thin terminal client over the
existing loopback Control API. It does not add a second execution engine, state store, policy engine,
or approval authority.

## Scope

The V1 TUI supports exactly one governed flow:

```text
Agent catalog
→ tool-free Agent selection
→ governed preflight
→ exact confirmation
→ persisted Run SSE
→ terminal Run
→ ROOT Invocation
→ verified Artifact
→ recorded Evaluation
```

Supported Agents must be:

- `session_mode=disabled`;
- `workspace_access=none`;
- no Function Tool;
- no MCP;
- no Handoff;
- no Agent-as-Tool;
- no Guardrail.

## Architecture

New product-owned package:

```text
src/okcanvas_agent_runtime/tui_client/
  config.py   loopback URL and separated authority validation
  client.py   existing REST and persisted SSE adapter
  sse.py      bounded SSE parser
  app.py      terminal flow and rendering
```

Windows launchers:

```text
sh_run_api.cmd   existing Control API process
sh_tui.cmd       new TUI process
```

The TUI obtains local administrator and Run-submitter keys only from the process environment or
non-echo terminal prompts. It never writes them to disk and never embeds them in a URL.

## Runtime authority boundary

The Control API remains the only authority for:

- Agent definition resolution;
- model and Runtime binding selection;
- preflight persistence;
- confirmation validation;
- Task/Run creation;
- execution;
- Event persistence;
- Artifact verification;
- recorded Evaluation.

The TUI must not import or access `SQLiteProductStore`, execution gateways, protected payloads,
Session history, Agent SDK Runner, Tool implementations, or Runtime binding calculators.

## SSE boundary

STEP056 consumes only `/v1/runs/{run_id}/events/stream`, the existing persisted and cursor-addressable
SSE endpoint. Native SDK streaming remains process-local and is not required by this foundation.
The TUI validates every streamed `run_id` and fetches the terminal Run after stream completion.

## Exact confirmation

The TUI displays the server-issued confirmation challenge and compares the typed value locally with
constant-time comparison before calling the confirmation endpoint. The server remains authoritative
and validates the same exact challenge again.

A local mismatch creates no Product Task or Run. The preflight Submission and encrypted payload
remain governed by the existing unconfirmed retention policy.

## Evaluation

A new deterministic case, `tui-client-foundation-v1`, evaluates the tool-free `coding-agent` result.
The TUI retrieves the verified Artifact through the existing read API and requests a recorded
Evaluation through the existing endpoint.

## Deterministic acceptance

`scripts/run_step056_acceptance.py` starts the real loopback FastAPI/uvicorn Control API and proves:

- remote Control API URLs are rejected;
- admin and Run-submitter authorities remain distinct;
- the Agent catalog is loaded through HTTP;
- only V1-compatible Agents are exposed;
- wrong confirmation creates no Task/Run;
- normal confirmation schedules exactly one execution;
- persisted SSE is consumed from sequence 1 through terminal retention;
- one ROOT Invocation is visible;
- the Artifact is verified;
- the recorded Evaluation passes;
- the TUI has no direct Runtime/store import;
- credentials and raw request are not persisted;
- the successful payload is deleted and the unconfirmed payload remains;
- the HTTP client and acceptance workspace close cleanly;
- immutable References remain unchanged.

Deterministic result: 21/21 checks, exact Product counts `1/1/2/1/10/1/1`, one retained protected
payload, and cleanup `COMPLETED` in one attempt.

## Non-scope

STEP056 does not implement:

- SQLite Session selection or conversation history;
- approval inbox or approval decisions;
- Handoff/Agent-as-Tool tree visualization beyond returned Invocation rows;
- Tool or MCP Agent execution;
- native SDK text-delta streaming;
- cancellation or reconciliation actions;
- local DB inspection;
- config or secret persistence;
- remote Control API access;
- full-screen framework, mouse support, or plugin UI;
- Sandbox, filesystem, Shell, network, or workspace capability.

## Windows command

Run the API in one terminal:

```bat
sh_run_api.cmd
```

Run the TUI in a second terminal:

```bat
sh_tui.cmd --agent-id coding-agent --evaluation-case-id tui-client-foundation-v1
```

Deterministic Windows acceptance:

```bat
sh_run_step056_acceptance.cmd
```

STEP057 must not begin until STEP056 reports all checks and cleanup `COMPLETED` from the fresh ZIP.

## Windows startup correction after first manual use

The first manual `sh_run_api` attempt exposed an onboarding defect before TUI execution: the configured
protected-payload key was a placeholder that did not decode to 32 bytes. The app factory rejected it
correctly, but only after uvicorn startup with a long traceback. `.env.local.cmd.example` also lacked
the governed Run variables required by the TUI path.

The corrected package therefore:

- validates Control API local secrets before uvicorn starts;
- rejects example admin/submitter placeholders and non-32-byte payload keys without echoing them;
- prints the exact local key-generation command;
- aligns `.env.local.example`, `.env.local.cmd.example`, and `.env.example`;
- preserves the existing Product key parser and encryption contract unchanged.

This is a STEP056 onboarding/launcher correction, not STEP057 functionality.
