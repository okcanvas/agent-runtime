# STEP049 — SQLite Session Native Agent-as-Tool Composition V1

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Version `2.29.0`.

## Closed prerequisite

The user-reported Windows `sh_run_step048_acceptance` output exactly matched all 32 STEP048 conditions. STEP048 is now `WINDOWS_LIVE_ACCEPTED`: Session metadata remained `1/2` across both rejected Guardrail Turns and completed at `2/4`; streamed/model/Guardrail/Session counts were `4/3/4·3/8·8`; final Product counts were `4/4/4/4/43/2/1`; protected payload count was two; Reference integrity and cleanup completed.

## Problem

STEP042 native Agent-as-Tool and STEP043 SQLite Session were independently Windows-live accepted, but every product boundary rejected their composition. A Session-enabled Root could not delegate to the existing terminal Agent-as-Tool child. The missing contract was not a new child runtime: it was exact ownership of conversational history, Turn lease, nested Session isolation, Runtime binding and rollback.

Passing the Root Session into the nested child would give two Agent scopes authority over one conversational history and make nested Turn accounting ambiguous. Conversely, allowing the Root to commit after a failed nested child could preserve a partial Tool call or Tool result in SDK history. STEP049 closes both risks.

## Goal

Permit one exact composition:

- one installed-SDK `sqlite-v1` Session on the Root Agent;
- exactly one immutable native Agent-as-Tool child;
- child nested execution always `session=None`;
- child terminal at depth one, language-only and workspace-free;
- one Agent-as-Tool call per successful Product Turn;
- success commits the complete Root SDK Turn;
- failure rolls Root SDK history back to the captured pre-Turn item boundary;
- safe Product Session and invocation evidence only.

## Accepted graph

```text
session-agent-tool-manager-agent
├─ session_mode = sqlite-v1
└─ invoke_agent_tool_specialist_agent
   └─ agent-tool-specialist-agent
      ├─ session_mode = disabled
      ├─ terminal depth = 1
      └─ workspace_access = none
```

Both Agents use `CodingAgentResult`. Neither owns Function Tools, MCP, Handoffs, Guardrails, files, Shell, network or workspace capability.

## Product contracts

1. Runtime execution path is exactly `sqlite-session-native-agent-tool-execution-v1`.
2. Runtime binding includes the SQLite Session policy, STEP049 composition policy, existing Agent-as-Tool policy, Root and child definition SHAs, child Runtime binding SHA, Session Runtime SHA, Agent-as-Tool Runtime SHA and execution-engine SHA.
3. Product Session creation pins the Root definition SHA and composed Runtime binding SHA.
4. The governed request fingerprint, confirmation and protected payload bind the exact Product Session ID.
5. Product acquires one Root active-Turn lease and captures the pre-Turn SDK item count before calling `Runner.run_streamed(session=SQLiteSession)`.
6. The installed SDK builds the declared child through `Agent.as_tool`; the nested run receives `session=None` and an explicit child `RunConfig` that does not inherit the parent RunConfig.
7. One successful Turn creates exactly one ROOT and one AGENT_AS_TOOL invocation, one bounded structured child result and one final Artifact.
8. Parent control is retained after child completion. The child cannot transfer control, add descendants or acquire a workspace.
9. A successful Turn commits the complete Root SDK history, increments Product `turn_count` once and synchronizes `item_count`.
10. Any parent or nested child failure removes every Root SDK item after the captured pre-Turn boundary before releasing the lease; `turn_count` does not increase.
11. Confirmation replay schedules no second execution and creates no duplicate child invocation, history, Artifact or Evaluation.
12. Raw Session history, requests, Agent Tool arguments/results, nested model output, prompts, instructions, reasoning, API keys and SDK objects are not Product Event or Product/Evaluation payloads.

## Explicit non-scope

- a Session-enabled Agent-as-Tool child;
- sharing the Root Session object with the child nested run;
- more than one child, more than one Agent Tool call, nesting deeper than one or parallel children;
- Handoff, Function Tool, approval, MCP or Guardrail mixed with this composition;
- child workspace, filesystem, Shell, network, hosted Tool, Sandbox or secret capability;
- child process-loss resume, retry, fallback or partial-result aggregation;
- remote Session backend, distributed Turn lease, encryption, compaction or export;
- cross-database atomic transaction claims.

## Deterministic acceptance

Run:

```text
python scripts/run_step049_acceptance.py
```

The acceptance executes two governed Product Turns on one Session:

1. Turn one begins with no history, calls the declared child once, commits a four-item Tool conversation and Session metadata `1/4` while storing marker `AURORA-49`;
2. Turn two receives the complete first Turn, calls the same terminal child once, proves continuity through the final Artifact and commits `2/8`.

Required result:

- 33/33 checks true;
- outer `Runner.run_streamed=2`, nested Agent Tool streaming invocations `2`, `Runner.run=0`;
- `Agent.as_tool` constructions/invocations `2/2`;
- Root Session identities `2`, child nested Sessions `[None, None]`;
- SQLiteSession instances/closes `4/4`;
- one Agent Tool start/completion pair per Turn;
- ROOT/AGENT_AS_TOOL invocations `2/2`, all succeeded and child depth one;
- Event counts `20/20`, total `40`;
- final Task/Run/Submission/Invocation/Event/Artifact/Evaluation `2/2/2/4/40/2/1`;
- Session `1/4 → 2/8`, exact history item count `8`;
- protected payload count zero;
- Reference unchanged and cleanup `COMPLETED`.

## Windows harness correction after first live attempt

The first Windows execution passed all 32 functional checks and reported `state_before_workspace_cleanup=PASSED`, but the overall state was `FAILED` because `cleanup_completed=false`. `AcceptanceWorkspace` preserved the workspace after three deletion attempts with WinError 32 on `scratch/sessions/history.sqlite3`.

The exact source defect was the acceptance-only history count probe:

```python
with sqlite3.connect(runtime.history_db) as history_conn:
    ...
```

`sqlite3.Connection.__enter__/__exit__` controls transaction commit/rollback; it does not close the connection. The corrected implementation calls a dedicated `_history_count` helper whose `finally` block always invokes `connection.close()`. A regression test injects a fake connection and proves `close()` is called. Product Session handles had already closed exactly `4/4`; no Product execution or Session continuity contract failed.

The failed Windows evidence is retained in `docs/evidence/STEP049_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json`. A fresh corrected-ZIP rerun is required.

## Windows closure gate

From a fresh extracted ZIP:

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step049_acceptance.cmd
```

Do not select or implement STEP050 until this complete Windows result is reported and recorded.
