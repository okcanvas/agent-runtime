# STEP046 SQLite Session Approval Composition V1

## Status

`WINDOWS_LIVE_ACCEPTED`

Executable baseline: `STEP046_SQLITE_SESSION_APPROVAL_COMPOSITION_V1`, version `2.26.0`.

## Why this STEP follows the P0 skeleton

After STEP045 Windows closure, the P1 candidates were re-audited against code and immutable Reference. Session plus approval is the smallest high-value composition that reuses two already-live product boundaries without introducing a new network transport, parallel cancellation model, or arbitrary-code isolation provider.

Current code before STEP046 rejected every Session Agent with a Function Tool. The approval Gateway also passed `session=None` on both prepare and resume. Therefore a conversational Turn could not remain attached to one SDK Session while waiting for an operator decision.

The installed SDK Reference already proves the underlying primitive:

- `tests/test_hitl_session_scenario.py` runs approved and rejected Tool Turns through one Session;
- `tests/test_run_impl_resume_paths.py::test_resumed_approval_does_not_duplicate_session_items` proves one function call and one function output after resume, not duplicated history.

The product Runtime still needed its own Session identity, Turn lease, protected-payload binding, approval ledger identity, canonical evidence, retention, and failure rollback.

## V1 product contract

One immutable Agent is added:

```text
session-approval-agent
├─ session_mode=sqlite-v1
├─ tool=local_text_metrics
├─ approval_mode=ALWAYS
├─ workspace_access=none
└─ no MCP, Handoff, Agent-as-Tool or Guardrail
```

One immutable composition policy is added:

```text
specs/runtime/sqlite-session-approval-policy.json
```

Exact policy:

- one Function Tool;
- approval mode `ALWAYS`;
- hold the active Session Turn lease while interrupted;
- approved Turn commits;
- rejected conversational Turn also commits the rejection outcome;
- failed/integrity-corrupt Turn rolls history back to the item boundary captured before prepare;
- no workspace.

## Lifecycle

### Prepare

```text
Session ACTIVE
→ governed preflight binds session_id
→ protected payload binds session_id
→ Product Task/Run and ROOT invocation
→ acquire Session active-Turn lease
→ SDK Runner prepare with session=
→ SDK history 0→2 items for the Turn prefix
→ encrypted RunState + approval ledger
→ Product Run INTERRUPTED
→ Session remains ACTIVE with active_run_id held
```

Clear and another active Turn fail while the approval is pending.

### Approve

```text
approval decision APPROVE
→ verify approval/submission/payload/session identity
→ verify active Session lease belongs to same Product Run
→ SDK resume with the same session=
→ Tool executes exactly once
→ SDK history 2→4 items
→ Session Turn commits and lease releases
→ Artifact + Product Run SUCCEEDED
→ recorded Evaluation may run
→ successful protected payload deleted
```

Decision replay returns the terminal result without another SDK resume, Tool call, Session item, Turn increment or Artifact.

### Reject

```text
approval decision REJECT
→ SDK resume with same session=
→ Tool executes zero times
→ rejection output is committed to Session history
→ Session Turn commits and lease releases
→ Product Run CANCELLED
→ no Artifact/Evaluation
→ protected payload retained for investigation
```

Decision replay is likewise a no-op.

### Failure

State-integrity or resume failure:

```text
rollback SDK history to session_item_count_before
→ release active Turn without increment
→ Product Run/Task/ROOT invocation FAILED
→ approval FAILED
→ existing failure retention
```

## Runtime binding

`sqlite-session-approval-execution-v1` binds:

- Session policy;
- Session+approval composition policy;
- Agent Definition and output contract;
- Function Tool definition, policy, schemas and implementation;
- approval Gateway/service/store and encrypted RunState path;
- Session service and implementation;
- invocation scope and execution engine.

Any drift requires a new preflight and exact confirmation boundary.

## Product evidence

Safe canonical Session events for each Turn:

```text
session.turn.started
session.turn.interrupted
session.turn.completed
```

They contain Session identity, item counts, Turn number, outcome and explicit no-history-copy evidence. Raw Session history, request text, Tool arguments/results, RunState, API keys and secrets do not enter Product Events or Product/Evaluation SQLite.

Approval inbox metadata exposes `session_id` so an operator can see which conversation is blocked. It does not expose Session history.

## Deterministic acceptance

STEP046 executes two Turns in one Session:

1. approved Turn;
2. rejected Turn.

Expected exact transitions:

```text
created                 ACTIVE 0/0
approve interrupted     ACTIVE 0/2, active_run_id set
approve completed       ACTIVE 1/4, active_run_id null
reject interrupted      ACTIVE 1/6, active_run_id set
reject completed        ACTIVE 2/8, active_run_id null
```

Expected external behavior:

- prepare/resume `2/2`;
- Session instances/closes `10/10`;
- approved Tool execution `1`;
- rejected Tool execution `0`;
- both decision replays no-op;
- approved Artifact/Evaluation `1/1`;
- final Task/Run/Submission/Invocation/Event/Artifact/Approval/Evaluation `2/2/2/2/37/1/2/1`;
- one rejected payload remains;
- References unchanged;
- cleanup completed.

## Explicit non-scope

- Session + Handoff;
- Session + Agent-as-Tool;
- Session + MCP;
- Session + Guardrail;
- more than one approval Tool;
- multiple interruptions in one Turn;
- remote/distributed Session backend or distributed lease;
- Session history encryption/compaction/export;
- in-flight process-loss auto-resume or approval timeout automation;
- file capability, Sandbox, Shell or network;
- cross-database atomic transaction claim between Product and Session SQLite.

The last item remains an explicit V1 operational boundary: ordering is fail-closed and deterministic, but no distributed transaction is claimed.

## Windows gate

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step046_acceptance.cmd
```

Do not select the next executable STEP until every STEP046 check is true and cleanup is `COMPLETED`.
