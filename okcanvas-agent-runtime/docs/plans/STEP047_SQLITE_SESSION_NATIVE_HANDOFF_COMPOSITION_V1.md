# STEP047 — SQLite Session Native Handoff Composition V1

## Status

`WINDOWS_LIVE_ACCEPTED`

Version `2.27.0`.

## Problem

STEP041 native Handoff and STEP043 SQLite Session were independently accepted, but the product explicitly rejected their composition in the Agent catalog, Runtime binding, generic execution preflight, Session creation API, and OpenAI gateway. The SDK itself supports a Session across Handoff execution, but product identity, Turn lease, rollback, invocation, Event, and replay contracts had not been closed.

## Goal

Permit one exact composition:

- one `sqlite-v1` root Session;
- one immutable native Handoff child;
- one terminal child at depth one;
- the same SDK SQLiteSession across the transfer and later Turns;
- complete successful Turn commit and failed partial-history rollback;
- safe Product Events and exact invocation identity.

## Accepted graph

```text
session-handoff-triage-agent (ROOT, sqlite-v1)
  └─ native Handoff exactly once
       └─ handoff-specialist-agent (HANDOFF, terminal, Session-disabled)
```

Both definitions use `CodingAgentResult` and `workspace_access=none`.

## Product contracts

1. Runtime binding path is exactly `sqlite-session-native-handoff-execution-v1`.
2. Binding includes SQLite Session policy, STEP047 composition policy, native Handoff policy, both Runtime source SHAs, child definition closure, invocation policy, and execution-engine SHA.
3. Session creation pins root Agent definition SHA and the composed Runtime binding SHA.
4. Run preflight requires the exact Product Session ID and binds it into the request fingerprint and protected payload.
5. The Turn lease is acquired before root execution and held through child completion, Artifact registration, and Session commit.
6. One successful Turn adds four deterministic acceptance items: user, Handoff call, Handoff output, assistant.
7. Failure/cancellation rolls SDK history back to `item_count` captured at lease acquisition and releases without incrementing `turn_count`.
8. Handoff creates one depth-one child invocation; root and child usage remain partitioned through the existing STEP041 ledger.
9. `agent.handoff` adds only safe booleans proving SDK Session history was active and a Session identity was present.
10. Raw requests and Session history stay in protected payload/SDK Session storage, never canonical Product or Evaluation storage.
11. Exact confirmation replay returns the same Run and schedules no execution.

## Explicit non-scope

- Session + Agent-as-Tool, MCP, Guardrail, or a second/mixed Function Tool;
- multiple, nested, dynamic, or parallel Handoffs;
- child Session identity or independent child history;
- physical workspace, file, Shell, network, secret, or Sandbox capability;
- process-loss automatic resume, remote Session backend, distributed lease, encryption, compaction, export;
- cross-database atomic transaction claims.

## Deterministic acceptance

`python scripts/run_step047_acceptance.py`

Required:

- 29/29 checks true;
- two Runs, each exactly one Handoff;
- Session `0/0 → 1/4 → 2/8`;
- two ROOT and two HANDOFF invocations;
- final Product counts `2/2/2/4/32/2/1` for Task/Run/Submission/Invocation/Event/Artifact/Evaluation;
- replay schedules nothing;
- clear and competing Turn fail while lease held;
- handles close, protected payload count zero, References unchanged, cleanup completed.

## Windows closure gate

Run `sh_run_step047_acceptance.cmd` after `sh_setup.cmd` from a fresh ZIP extraction. Until the output is reported and recorded, this STEP is not Windows live accepted and no STEP048 is selected.
