# STEP049 Code and Immutable Reference Audit

## Audit rule

STEP049 was selected only after inspecting the packaged STEP048 product source and immutable `reference/upstream/openai-agents-python-0.19.0` snapshot. Runtime source imports nothing from `/reference`.

## STEP048 Windows closure

The user-reported Windows JSON was compared with `docs/evidence/STEP048_ACCEPTANCE.json`, the STEP048 plan and validation contract. All 32 booleans, four Session metadata checkpoints, gateway and Guardrail counts, Event counts, Product counts, payload retention, Evaluation, Reference integrity and acceptance workspace cleanup matched. The compact record is `docs/evidence/STEP048_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.

## Candidate comparison after closure

### Selected: SQLite Session + native Agent-as-Tool

- SQLite Session and Agent-as-Tool primitives were already Windows-live accepted independently.
- Existing STEP042 already owns the exact child graph, invocation ledger, terminal depth-one restriction, explicit child RunConfig, bounded structured result and `session=None` nested execution.
- Existing STEP043/046/047/048 code already owns Product Session identity, Turn lease, pre-Turn item boundary, success commit and failure rollback.
- The composition introduces no new network transport, filesystem, Sandbox, side-effecting Tool or concurrency boundary.
- It gives a concrete conversational capability: a Session Root can repeatedly consult a specialized Agent while retaining one Root-owned conversation.

### Deferred: MCP breadth

Remote transport ownership, authentication, resources/prompts, reconnect, timeout and remote failure evidence remain unresolved.

### Deferred: bounded orchestration

Parallel child start/cancel, concurrency ceilings, partial failure, deterministic aggregation and process-loss behavior remain unresolved.

### Deferred: model/provider policy

Immutable routing, fallback authority, provider identity, pricing/latency evidence and replay binding remain unresolved.

### Deferred: file/Shell/Sandbox capability

A host directory is not containment. Provider lifecycle, mounts, egress, secrets, cleanup and Artifact export must be designed first.

### Deferred: Session hardening

Encryption, compaction, remote backend, distributed lease and process-loss recovery are broader lifecycle changes than this closed composition.

## Product code findings before change

1. `agent_definitions/catalog.py` rejected every SQLite Session definition containing `agent_tools`.
2. `sessions/service.py` rejected Session creation whenever any Agent-as-Tool child existed.
3. `execution/runtime_binding.py` classified ordinary Agent-as-Tool only when Session was disabled and classified SQLite Session only when Agent-as-Tool was absent.
4. `execution/openai_gateway.py` rejected Session+Agent-as-Tool before building SDK objects.
5. `execution/service.py` accepted only the isolated STEP042 path for child graphs and omitted STEP049 from Session preflight.
6. `run_submission/service.py` and `control_api/app.py` omitted any Session Agent-as-Tool path.
7. Failed Session rollback was activated for Handoff and Guardrail compositions, but not Agent-as-Tool.
8. Existing `build_sdk_agent_tool` already passed `session=None` to `Agent.as_tool`, retained parent control, generated an explicit child `RunConfig`, bounded child output and emitted safe lifecycle metadata.

## Immutable SDK findings

Primary inspected paths:

- `src/agents/agent.py`, especially `Agent.as_tool(...)`;
- `src/agents/run.py` and streamed Runner entry points;
- Agent-as-Tool tests and Session persistence tests in the immutable upstream snapshot.

Observed behavior:

- `Agent.as_tool` accepts an explicit `session` argument for the nested Runner call.
- The SDK default is `session=None`; the product can and must preserve that for the STEP049 child.
- The outer Root Runner independently accepts the installed-SDK Session.
- Agent-as-Tool returns to the parent rather than transferring control, unlike Handoff.
- SDK Session persistence belongs to the outer Runner. Product code must not copy child output into a second Session or infer Product Turn completion solely from item presence.

## Adopted design

- immutable `sqlite-session-agent-tool-policy.json`;
- dedicated `SQLiteSessionAgentToolPolicyCatalog`;
- exact one-child/depth-one Root-only Session validator;
- new composed Runtime path and policy/implementation fingerprints;
- unchanged STEP042 child construction with `session=None`;
- unchanged invocation ledger and safe `agent.tool.started/completed` Event mapping;
- pre-Turn Root history rollback for every failed Session Agent-as-Tool execution;
- two-Turn deterministic acceptance proving Root continuity and child Session isolation.

## Deliberately rejected

- passing the Root SQLiteSession into `Agent.as_tool`;
- granting the child a Product Session or separate persistent child Session;
- preserving partial outer Tool-call history after nested failure;
- weakening ordinary STEP042 or earlier Session composition validators;
- copying raw nested arguments/results or Session history into Product evidence;
- claiming nested/parallel orchestration, arbitrary capability mixing, process-loss resume or distributed atomicity.

## Acceptance implementation audit

The first STEP049 run exposed two harness defects rather than product failures:

1. Session creation still contained one product restriction that rejected `agent_tools`; this was a real missing product boundary and was corrected with an exact one-child composition predicate.
2. The new acceptance called a nonexistent `count_items_sync` helper. It was changed to inspect the deterministic fake SDK history database directly after all SDK handles closed, avoiding an extra handle that would corrupt the intended `4/4` close-count proof.

The corrected deterministic acceptance passed all 33 checks with cleanup `COMPLETED`.

The first real Windows run then exposed a third acceptance-harness defect that Linux did not reveal:

3. The direct fake-history verification used `with sqlite3.connect(runtime.history_db)`. The SQLite connection context manager does not close the connection; it only commits or rolls back. Windows therefore kept `history.sqlite3` locked and `AcceptanceWorkspace` preserved the workspace after three cleanup attempts. Every non-cleanup check, Product count, Session count, Evaluation and the instrumented SDK Session close count `4/4` had passed. The history probe is now isolated in `_history_count(...)` with `connection.close()` in `finally`, and a dedicated regression test proves closure.

This finding does not authorize `WINDOWS_LIVE_ACCEPTED`; a fresh corrected-package Windows rerun is still required.
