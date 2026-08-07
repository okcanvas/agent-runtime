# STEP047 Code and Immutable Reference Audit

## Audit rule

This decision was made only after inspecting the packaged product source and the immutable `reference/upstream/openai-agents-python-0.19.0` snapshot. No executable code imports from `/reference`.

## Product code findings before change

1. `agent_definitions/catalog.py` rejected every Session Agent with a Handoff.
2. `execution/runtime_binding.py` classified native Handoff only when `session_mode=disabled` and tool-free Session only when child-free.
3. `execution/openai_gateway.py` rejected Session+Handoff before constructing SDK Agents and always used the STEP041 validator requiring both definitions to be Session-disabled.
4. `execution/service.py` allowed only `sqlite-session-execution-v1` during Session preflight and only `native-handoff-execution-v1` during Handoff preflight.
5. `run_submission/service.py` and `control_api/app.py` allowed Session creation/submission only for STEP043 or STEP046 paths.
6. Generic failed Session Turns released the lease with the observed partial history count; no composition-specific rollback to the pre-Turn boundary existed.
7. Existing invocation and lifecycle code already created ROOT/HANDOFF identities, partitioned usage, held the Session Turn lease until gateway completion, and committed Session metadata after Artifact creation.

## Immutable SDK findings

Primary paths inspected:

- `src/agents/memory/sqlite_session.py`
- `src/agents/run_internal/session_persistence.py`
- `src/agents/handoffs.py` and Handoff runtime paths listed by `reference/CODE_MAP.md`
- `tests/test_handoff_history_duplication.py`
- `tests/test_soft_cancel.py`
- `tests/test_agent_runner.py`
- `tests/test_hitl_session_scenario.py`
- `tests/test_run_impl_resume_paths.py`

Observed upstream behavior:

- Runner accepts one Session object while the active Agent changes through a Handoff.
- Handoff input filtering and history partitioning are SDK responsibilities.
- upstream tests exercise Handoff history duplication prevention, pending Handoff survival, nested history partition/resume, and soft cancellation with SQLite Session.
- Session persistence is staged and deduplicated by SDK item identity rather than product-side prompt concatenation.

## Candidate comparison

### Selected: SQLite Session + native Handoff

- both product primitives already Windows-live accepted;
- direct upstream combined coverage exists;
- no new external transport, filesystem, Sandbox, or parallel cancellation provider;
- existing Product invocation and Session lease services cover most lifecycle work.

### Deferred: MCP breadth

Requires remote transport ownership, authentication, resources/prompts, reconnect and error policy beyond the local read-only MCP path.

### Deferred: bounded orchestration

Requires concurrency limits, cancellation propagation, child partial failure, deterministic aggregation, and process-loss semantics.

### Deferred: model/provider policy

Requires immutable selection/fallback authority and cost/latency/replay evidence, not only a configuration field.

### Deferred: file capability/Sandbox

Requires a real containment provider, mounts, egress, secrets, cleanup and Artifact export. Host folders are not sufficient isolation.

## Adopted product design

- new immutable `sqlite-session-handoff-policy.json` and parser;
- separate `validate_sqlite_session_handoff_definitions` without weakening STEP041;
- new composed Runtime binding path and combined source fingerprints;
- exact root/child capability closure;
- same SDK Session passed through existing gateway;
- failed history rollback to lease-acquisition item count;
- safe Session-presence metadata on `agent.handoff`;
- two-Turn deterministic acceptance with replay and lease-contention probes.

## Deliberately rejected

- manually concatenating Session history into prompts;
- copying raw Handoff/Session history into Product Events;
- enabling child-owned Session IDs;
- dynamic Handoff destinations;
- weakening the old STEP041 validator;
- claiming process-loss resume, distributed atomicity, or arbitrary composition.
