# STEP050 — SQLite Session Native MCP Composition V1

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Version `2.30.0`.

## Closed prerequisite

The corrected STEP049 Windows launcher result exactly matched all 33 packaged conditions. STEP049 is now `WINDOWS_LIVE_ACCEPTED`: Session `1/4 → 2/8`, outer/nested streaming `2/2`, Agent-as-Tool construction/invocation `2/2`, SQLiteSession instances/closes `4/4`, final Product counts `2/2/2/4/40/2/1`, no protected payload files, Evaluation `PASSED`, Reference unchanged and workspace cleanup `COMPLETED` in one attempt. The earlier Windows cleanup failure remains preserved separately as evidence of the corrected Acceptance-only SQLite handle leak.

## Problem

The product had independently accepted SQLite Session and one allowlisted read-only local stdio MCP server, but every Session-enabled Agent definition containing MCP was rejected. The missing contract was exact ownership and cleanup ordering across three lifecycles:

1. the Product Session Turn lease and SDK history;
2. the per-Turn MCP manager and local stdio server;
3. Product Run terminalization, payload retention and workspace cleanup.

A successful MCP Turn must commit the entire SDK Tool conversation. A failed MCP call may leave partial user, Tool-call or Tool-result items in SDK history. Product code therefore must finish MCP manager cleanup first, roll history back to the captured pre-Turn item boundary, and only then release the Session Turn lease.

## Goal

Permit one exact composition:

- one installed-SDK `sqlite-v1` Session;
- exactly one product-owned allowlisted MCP server, `reference-catalog`;
- transport exactly local `builtin-stdio`;
- read-only Tool surface only;
- MCP manager scope exactly one Product Turn;
- success commits one complete MCP Tool conversation;
- MCP/Runner failure rolls SDK history back to the pre-Turn boundary after manager exit;
- safe Product Event metadata only.

## Accepted graph

```text
session-reference-research-agent
├─ session_mode = sqlite-v1
├─ mcp_servers = [reference-catalog]
├─ workspace_access = none
└─ no Function Tool / approval / Handoff / Agent-as-Tool / Guardrail
```

`reference-catalog` remains the existing immutable read-only local stdio MCP definition. STEP050 does not add a remote server, resources, prompts, filesystem authority or arbitrary command selection.

## Product contracts

1. Runtime execution path is exactly `sqlite-session-native-mcp-execution-v1`.
2. Runtime binding includes SQLite Session policy, STEP050 MCP composition policy, MCP server definition and module fingerprints, Session Runtime and execution-engine fingerprints.
3. Product Session creation pins the exact Agent-definition and composed Runtime-binding SHA.
4. Governed preflight, confirmation, protected payload and execution bind the same Product Session ID.
5. Product acquires one active-Turn lease and captures pre-Turn SDK item count before constructing the per-Turn MCP runtime.
6. Each Turn constructs exactly one `reference-catalog` local stdio server and enters exactly one MCP manager scope.
7. The installed SDK receives the same SQLiteSession and the manager-owned MCP server list through `Runner.run_streamed()`.
8. A successful Turn exits the MCP manager, persists one complete four-item MCP Tool conversation, creates one Artifact, commits Session metadata and increments `turn_count` once.
9. A failed MCP/Runner Turn exits the MCP manager first, removes every SDK item after the captured pre-Turn boundary, does not create an Artifact or Evaluation, does not increment `turn_count`, and releases the lease.
10. Confirmation replay schedules no second execution and appends no Session history.
11. Product Events expose only safe server ID, Tool name and lifecycle metadata. Query text, Tool arguments/results, Session history, prompts, instructions, reasoning, API keys and SDK objects are prohibited.
12. Successful protected payloads are deleted; the failed Turn payload follows the existing failed-run investigation retention policy.

## Explicit non-scope

- remote MCP transport, HTTP/SSE reconnect, OAuth or tenant credentials;
- MCP resources, prompts, subscriptions, sampling or server-initiated behavior;
- more than one MCP server or more than one MCP Tool call per Turn;
- write-capable or side-effecting MCP Tools;
- Function Tool, approval, Handoff, Agent-as-Tool or Guardrail mixed with this composition;
- workspace, file, Shell, network egress authority, hosted Tool or Sandbox capability;
- automatic retry/fallback, process-loss resume or manager resurrection;
- remote Session backend, encryption, compaction, distributed lease or distributed atomic transaction.

## Deterministic acceptance

Run:

```text
python scripts/run_step050_acceptance.py
```

The acceptance executes three governed Product Turns on one Session:

1. successful MCP Turn commits marker `COMET-50` and Session `1/4`;
2. MCP failure creates three partial history items, exits the second manager, rolls those items back and leaves Session `1/4`;
3. later successful Turn receives only the first committed history, proves the failed sentinel is absent and commits Session `2/8`.

Required result:

- 31/31 checks true;
- direct `Runner.run=0`, `Runner.run_streamed=3`, model calls `3`;
- MCP runtime/manager enter/manager exit/Tool call `3/3/3/3`;
- SQLiteSession instances/closes `6/6`;
- exact manager ordering proves `manager_exit_2` precedes every `rollback_pop_2`;
- Event counts `14/11/14`, total `39`;
- final Task/Run/Submission/Invocation/Event/Artifact/Evaluation `3/3/3/3/39/2/1`;
- Session `1/4 → 1/4 → 2/8`, exact history item count `8`;
- protected payload count `1`;
- Evaluation `PASSED`, Reference unchanged and cleanup `COMPLETED`.

## Windows closure gate

From a fresh extracted ZIP:

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step050_acceptance.cmd
```

Do not select or implement STEP051 until the complete Windows result is reported and recorded.
