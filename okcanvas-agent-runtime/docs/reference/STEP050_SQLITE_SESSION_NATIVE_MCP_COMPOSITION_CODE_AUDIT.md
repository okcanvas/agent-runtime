# STEP050 Code and Immutable Reference Audit

## Audit rule

STEP050 was selected only after inspecting the corrected STEP049 packaged source and immutable `reference/upstream/openai-agents-python-0.19.0` snapshot. Executable Runtime code imports nothing from `/reference`.

## STEP049 Windows closure

The corrected user-reported Windows JSON was compared with the packaged STEP049 plan, Acceptance and exact gateway/Product/cleanup contract. All 33 booleans, Session checkpoints, outer and nested Runner counts, Agent-as-Tool counts, invocation structure, Evaluation, payload deletion, Reference integrity and `AcceptanceWorkspace` cleanup matched. The compact record is `docs/evidence/STEP049_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`; the earlier WinError 32 attempt remains in `STEP049_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json`.

## Candidate comparison after closure

### Selected: SQLite Session + existing read-only local stdio MCP

- SQLite Session was Windows-live accepted in STEP043 and repeatedly exercised in STEP046–049.
- The product-owned `reference-catalog` MCP was already independently live accepted and is read-only, local stdio, allowlisted and workspace-free.
- Existing MCP code already owns server definition validation, runtime construction, manager lifecycle and safe Tool Events.
- Existing Session code owns identity, one active-Turn lease, exact pre-Turn item boundary, success commit and failed-Turn rollback.
- The missing work is a narrow composition and cleanup-order contract, not a new remote transport or broad MCP platform.

### Deferred: remote MCP breadth

Authentication, remote transport ownership, reconnect, timeout, resources/prompts and remote failure evidence remain unresolved.

### Deferred: bounded orchestration

Concurrency ceilings, parallel cancellation, partial failure and deterministic aggregation remain unresolved.

### Deferred: model/provider policy

Immutable routing, fallback authority, provider identity, pricing and replay binding remain unresolved.

### Deferred: file/Shell/Sandbox capability

Containment provider, mount policy, egress, secrets, cleanup and Artifact export require an independent design.

### Deferred: Session hardening

Encryption, compaction, remote backend, distributed lease and process-loss recovery are broader lifecycle changes.

## Product code findings before change

1. `agent_definitions/catalog.py` rejected every Session definition containing `mcp_servers`.
2. `sessions/service.py` rejected Session creation whenever MCP was declared.
3. `execution/runtime_binding.py` classified MCP only when Session was disabled and classified SQLite Session only when MCP was absent.
4. `execution/openai_gateway.py` rejected Session+MCP before constructing SDK objects.
5. `execution/service.py`, `run_submission/service.py` and `control_api/app.py` omitted a composed execution path.
6. Failed Session rollback covered Handoff, Agent-as-Tool and Guardrail compositions but not MCP.
7. Existing MCP runtime already uses an async manager scope and safe product-owned server definitions, so no parallel MCP implementation was needed.

## Immutable SDK findings

Primary inspected paths:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/run.py`;
- `src/agents/agent.py` for `mcp_servers`;
- `src/agents/run_internal/session_persistence.py`;
- `src/agents/mcp/server.py`, `manager.py` and `util.py`;
- `tests/mcp/test_runner_calls_mcp.py` and Session persistence tests.

Observed behavior:

- `Runner.run_streamed()` accepts an installed-SDK Session independently of an Agent's `mcp_servers`.
- Agent MCP servers are resolved during the same Runner execution and may produce Function Tool call/result items that belong to the outer Session history.
- MCP manager lifecycle is external resource ownership; Product code must not release the Product Turn lease or attempt workspace deletion before manager exit.
- Upstream tests independently cover MCP Tool invocation and Session persistence, but no upstream product test closes this exact governed Session+MCP composition. The product therefore owns the composed rollback and evidence contract.

## Adopted design

- immutable `sqlite-session-mcp-policy.json` and `SQLiteSessionMCPPolicyCatalog`;
- exact one-server/read-only/local-stdio validator;
- new `session-reference-research-agent` definition;
- composed Runtime binding with Session, MCP policy, server definition/module and execution-engine fingerprints;
- unchanged product-owned MCP runtime/manager construction;
- pre-Turn history rollback for every failed Session MCP execution;
- manager cleanup before rollback and lease release;
- three-Turn deterministic acceptance proving success continuity and failed-Turn exclusion.

## Deliberately rejected

- arbitrary or caller-selected MCP server lists;
- remote MCP or write-capable Tools;
- sharing raw MCP content with Product Event/Evaluation storage;
- retaining partial MCP Tool-call history after failure;
- weakening earlier non-composed MCP or Session validators;
- mixing Function Tools, approval, Handoff, Agent-as-Tool, Guardrails or workspace capability;
- claiming retry, reconnect, process-loss recovery or distributed atomicity.

## Acceptance implementation audit

The deterministic harness uses one fake installed-SDK SQLite history database and three per-Turn fake MCP managers. The failed second Turn intentionally persists three partial items before raising. The captured lifecycle order must show `manager_exit_2` before three `rollback_pop_2` operations. This proves resource cleanup precedes history rollback and lease release rather than merely checking the final item count.

The acceptance also verifies safe MCP Event metadata, no raw query/result persistence, exact payload retention, replay idempotency, clear/competing-Turn rejection, Session handle closure, Reference integrity and real `AcceptanceWorkspace.finalize()` cleanup.
