# STEP048 Code and Immutable Reference Audit

## Audit rule

The STEP was selected only after inspecting the packaged product source and immutable `reference/upstream/openai-agents-python-0.19.0` snapshot. Executable source imports nothing from `/reference`.

## STEP047 Windows closure

The user-reported Windows JSON was compared with `docs/evidence/STEP047_ACCEPTANCE.json` and the STEP047 plan. All 29 booleans, Session metadata, gateway counts, event counts, Product counts, payload count, Reference integrity and cleanup state matched exactly. The compact record is `docs/evidence/STEP047_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.

## Candidate comparison after closure

### Selected: SQLite Session + Agent input/output Guardrails

- SQLite Session and native Guardrail primitives are already Windows-live accepted.
- The composition adds no remote transport, child graph, arbitrary code, filesystem or external side effect.
- The immutable SDK has direct combined evidence in `tests/test_agent_runner_streamed.py::test_input_guardrail_streamed_does_not_save_assistant_message_to_session` and the adjacent sequential variants: a tripwire persists the user input but not the assistant message.
- Product already owns exact Session identity/lease/rollback and exact Guardrail failure/Event mapping; the missing work is a closed composition policy and rollback activation.
- Preventing rejected guarded input from contaminating later Session Turns is a concrete integrity need, not speculative breadth.

### Deferred: MCP breadth

Remote transport ownership, authentication, resources/prompts, reconnect, timeout and failure evidence remain unclosed.

### Deferred: bounded orchestration

Concurrency ceilings, child cancellation, partial failure, deterministic aggregation and process-loss semantics remain unclosed.

### Deferred: model/provider policy

Immutable routing/fallback authority, provider identity, price/latency evidence and replay binding remain unclosed.

### Deferred: file/Shell capability

A host directory is not containment. A real Sandbox provider, mounts, egress, secret injection, cleanup and Artifact export are required first.

### Deferred: Session hardening

Encryption, compaction, remote backend, distributed lease and process-loss recovery are larger lifecycle changes than the selected composition.

## Product code findings before change

1. `agent_definitions/catalog.py` rejected every Guardrail Agent whose `session_mode` was not disabled.
2. `execution/runtime_binding.py` classified Guardrails only as `native-guardrail-execution-v1` and rejected Session mode.
3. Its generic `sqlite_session` classifier did not explicitly exclude Guardrails, but the earlier Guardrail branch rejected the graph, so no executable composition existed.
4. `execution/openai_gateway.py` rejected Session+Guardrail both in initial Session validation and later Guardrail graph validation.
5. `execution/service.py` accepted only tool-free Session and STEP047 Handoff paths during Session preflight, and accepted only isolated STEP044 for a Guardrail graph.
6. `run_submission/service.py` and `control_api/app.py` omitted any Session Guardrail execution path.
7. Failed Session rollback was activated only for Session+Handoff; a Guardrail tripwire would otherwise release with observed partial item count.
8. Existing Guardrail failure mapping already emitted the four stable Product codes and safe `guardrail.tripped` metadata without guarded content.

## Immutable SDK findings

Primary inspected paths:

- `src/agents/run_internal/session_persistence.py`;
- `src/agents/run_internal/agent_runner_helpers.py`;
- `src/agents/run_internal/guardrails.py`;
- `tests/test_agent_runner_streamed.py` around input/output Guardrail streaming and Session persistence.

Observed behavior:

- Runner accepts `session=` together with Agent input/output Guardrails.
- On streamed input tripwire, SDK Session may contain the current user item while the assistant item is absent.
- Guardrail execution and Session persistence are SDK-owned; product code must not concatenate history or infer a successful Turn from item presence.
- Output Guardrail raises after model output. STEP048 acceptance deliberately persists a worst-case complete pair before raising, proving product rollback independently of a favorable SDK ordering.

## Adopted design

- immutable `sqlite-session-guardrail-policy.json`;
- dedicated `SQLiteSessionGuardrailPolicyCatalog`;
- exact Agent input/output kinds only, one each;
- new composed Runtime binding path and Session/Guardrail implementation fingerprints;
- existing installed-SDK `SQLiteSession` passed to `Runner.run_streamed`;
- pre-Turn item boundary rollback for every failed Session Guardrail execution;
- existing exact Guardrail codes and safe Event payload unchanged;
- four-case deterministic acceptance proving clean continuity and both rollback branches.

## Deliberately rejected

- Tool Guardrails or any Function Tool in STEP048;
- preserving rejected Guardrail Turn content in Session history;
- manually deleting only the latest guessed item instead of rolling back to a captured count;
- copying raw Session or Guardrail content into Product evidence;
- weakening isolated STEP044 or other composition validators;
- claiming arbitrary Guardrail/Session combinations, process-loss resume or distributed atomicity.

## Acceptance evidence correction found during final audit

The first STEP048 acceptance implementation set `cleanup_completed=true` inside the functional check map but did not call `AcceptanceWorkspace.finalize()`. That meant the functional 32-case result was valid, but workspace deletion was not actually evidenced. Final audit rejected that claim, changed the script to finalize the workspace, derive `cleanup_completed` from the returned lifecycle record, and rewrite the compact evidence only after cleanup. The corrected rerun passed 32/32 with `cleanup_state=COMPLETED`, one cleanup attempt, `resources_closed=true`, and the acceptance workspace path absent after execution. A baseline test now requires the finalize call.
