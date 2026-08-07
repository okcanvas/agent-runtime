# STEP043 — SQLite Session Runtime V1

## Status

- Executable baseline: `okcanvas-agent-runtime 2.23.0`
- STEP: `STEP043_SQLITE_SESSION_RUNTIME_V1`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`
- Previous Windows closure: STEP042 Agent-as-Tool Runtime V1 passed all 29 checks.

## Purpose

STEP043 adds the first product-governed conversation Session without combining it with any other advanced capability. One immutable tool-free Agent executes two separately governed Product Runs against the same installed-SDK `SQLiteSession`. Turn 2 must receive Turn 1 history automatically, while Product Task/Run/Event/Artifact/Evaluation state remains distinct from SDK Session history.

This is Session, not long-term memory. It is not a second Task/Run ledger and it does not turn conversation history into canonical Product Events.

## Code-audited upstream boundary

The installed SDK and immutable Reference show that:

- `Session` exposes asynchronous `get_items`, `add_items`, `pop_item`, and `clear_session`;
- `SQLiteSession(session_id, db_path=...)` persists per-session items in SQLite and has an explicit synchronous `close()`;
- Runner session persistence merges prior history with the new input and persists only the new turn items;
- the official SQLite example reuses one Session instance/identity across multiple `Runner.run` calls;
- the SDK does not provide Product authority, Agent-definition binding, Runtime-binding drift detection, an active-Turn lease, Product Session metadata, or governed clear authorization.

Therefore STEP043 adopts SDK history persistence and adds only product-owned governance around it.

## Product-owned Session metadata

A separate local SQLite catalog records:

- `session_id`;
- `ACTIVE`, transient `CLEARING`, or terminal `CLEARED` state;
- immutable Agent Definition ID/version/SHA;
- Runtime binding SHA;
- current `active_run_id` lease;
- successful `turn_count`;
- current SDK history `item_count`;
- create/update/clear timestamps.

Product metadata is stored in `catalog.sqlite3`. SDK conversation history is stored separately in `history.sqlite3`. They are different lifecycles and schemas.

## Agent and execution boundary

STEP043 adds `session-continuity-agent` with:

- `session_mode=sqlite-v1`;
- no Function Tool;
- no MCP;
- no Handoff;
- no Agent-as-Tool;
- `workspace_access=none`;
- `CodingAgentResult` output.

Its Runtime execution path is `sqlite-session-execution-v1`.

## Governed lifecycle

1. A caller with local-admin and Run-submitter authority creates a Session for one Session-enabled Agent.
2. Product code resolves and binds the exact Agent Definition and Runtime binding.
3. Governed preflight requires that Session ID and includes it in the request fingerprint.
4. Exact confirmation schedules the existing Product Task/Run path.
5. Before SDK execution, Product code acquires the Session's single active-Turn lease.
6. `Runner.run_streamed(..., session=<installed SDK SQLiteSession>)` executes the turn.
7. On success, Product code counts SDK history items, increments successful turn count, clears the active lease, writes safe Session Events, then completes the Product Run.
8. On failure or cancellation, the lease is released without incrementing successful turn count.
9. Explicit clear deletes SDK history and marks Product metadata `CLEARED` while preserving historical Product Runs/Artifacts/Evaluations.

## APIs

- `POST /v1/sessions` — local-admin plus Run-submitter; create for one Agent.
- `GET /v1/sessions` — local-admin; list metadata only.
- `GET /v1/sessions/{session_id}` — local-admin; read metadata only.
- `POST /v1/sessions/{session_id}/clear` — local-admin plus Run-submitter; explicit clear.
- governed preflight accepts optional `session_id`, but requires it exactly for `sqlite-v1` Agents and rejects it for Session-disabled Agents.

No API exposes the SDK history items in V1.

## Canonical Events

Each Session Turn adds exactly one pair:

- `session.turn.started` — Session ID, next turn ordinal, no-history-copy evidence, workspace none;
- `session.turn.completed` — Session ID, successful turn count, item count, no-history-copy evidence.

Raw history, new user input, prior assistant output, and Session database rows are prohibited from canonical Product Events.

## Runtime binding

The exact confirmation-bound Runtime fingerprint includes:

- SQLite Session policy;
- Session models, policy, and service implementation SHAs;
- generic governed execution, Gateway, streaming, output, and binding implementation SHAs;
- Agent Definition and execution path.

A Session is also pinned to the Agent Definition and Runtime binding that existed at creation. Drift causes fail-closed preflight/execution, not implicit migration.

## One-active-Turn rule

V1 permits exactly one active Product Run per Session. A second different Run receives `SESSION_BUSY`. Re-acquisition by the same Run is idempotent. Clear is rejected while a Turn is active.

## Interactive Runner

`/runner` now displays Session controls only for `sqlite-v1` Agents:

- list active Sessions for the selected Agent;
- create a Session;
- select a Session for governed preflight;
- clear a selected Session explicitly;
- show turn/item/active-run metadata.

The browser stores no Session history or request text. Session IDs remain tab-memory state and are not added to localStorage.

## Security and privacy boundary

- Session history is expected to contain conversation content in the separate SDK SQLite database.
- STEP043 does not encrypt that history and does not claim tenant-grade remote storage.
- Product SQLite and Evaluation SQLite do not receive raw history.
- canonical Events contain safe metadata only.
- API keys and protected payload plaintext remain excluded.
- no physical invocation workspace is created.

## Deterministic acceptance

`run_step043_acceptance.py` proves:

- authenticated Session create/list/read/clear;
- two governed preflights bound to one Session;
- `Runner.run_streamed` twice and `Runner.run` zero;
- same SDK Session ID both turns;
- Turn 1 starts with zero history and leaves two items;
- Turn 2 receives the two Turn 1 items and returns `ORBIT-7`;
- Product Session metadata `1/2`, then `2/4`;
- one canonical start/completion pair per Turn;
- two successful ROOT invocations with no workspace;
- one verified Turn-2 Artifact and one PASSED recorded Evaluation;
- active-Turn collision rejection;
- explicit clear to `CLEARED`, turn/item `2/0`;
- preflight after clear rejected;
- Product counts Task/Run/Submission/Invocation/Event/Artifact/Evaluation `2/2/2/2/24/2/1`;
- successful protected payload deletion;
- no raw history or API keys in Product/Evaluation DB;
- all SDK Session handles closed;
- unchanged References and cleanup `COMPLETED`.

## Explicit non-scope

STEP043 does not implement:

- Session with Handoff, Agent-as-Tool, MCP, Function Tool, approval or workspace;
- Session compaction, truncation or summarization;
- Session encryption;
- Redis, SQLAlchemy, Dapr, OpenAI Conversation or other remote backends;
- long-term semantic memory or RAG;
- parallel/concurrent Turns in one Session;
- history read/export UI;
- Session cloning, merge, retention scheduler or cross-process lease;
- process-loss auto-resume of a model Turn.

## Windows gate

Run:

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step043_acceptance.cmd
```

All 29 checks, two streamed Turns, exact metadata/counts, clear/reuse rejection, no workspace, successful payload cleanup and acceptance cleanup must pass before STEP044 begins.

## Next STEP

`STEP044_NATIVE_GUARDRAIL_RUNTIME_V1`

It must add official SDK input/output/Tool guardrail tripwire behavior without mixing Session into Guardrail acceptance and without conflating Pydantic contract validation with SDK Guardrails.
