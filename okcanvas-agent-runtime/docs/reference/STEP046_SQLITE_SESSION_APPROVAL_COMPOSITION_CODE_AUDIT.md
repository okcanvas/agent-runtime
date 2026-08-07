# STEP046 Code and Reference Audit

## Audited baseline

- Source: STEP045 Canonical ZIP, version `2.25.0`.
- P0 state: `BASIC_AGENT_RUNTIME_SKELETON_COMPLETE`, Windows live accepted.
- Rule: no speculation; current source and immutable Reference determine the P1 selection.

## P1 candidate comparison

### MCP breadth

`MCPServerCatalog` currently accepts the product-owned local `builtin-stdio` server. Streamable HTTP would add remote/network lifecycle, authentication, reconnect, cancellation and transport evidence. Valuable, but a larger failure surface.

### Bounded orchestration

Parallel fan-out is application-level composition, not a standalone SDK primitive. It first needs cancellation, partial failure, child result aggregation and bounded concurrency semantics. Higher architectural risk.

### Model policy

Retry/reasoning/provider policy is valuable but less immediately visible than making an already-supported conversation survive an approval interruption.

### File capability/Sandbox

A host folder is not hostile-code isolation. This candidate requires a real governed provider before enabling arbitrary file/Shell behavior and is deliberately deferred.

### Session + approval

The installed SDK and current product code already contain both halves. The missing composition was narrow, visible and testable. It was selected as STEP046.

## Current-code defect before STEP046

1. `AgentDefinitionCatalog` rejected any `sqlite-v1` Agent with a Tool.
2. `AgentRuntimeBindingCatalog` had only tool-free `sqlite-session-execution-v1` and Session-disabled approval execution.
3. `GovernedLocalToolApprovalService._validate_definition()` required `session_mode=disabled`.
4. `OpenAILocalToolApprovalGateway.prepare/resume()` explicitly passed `session=None`.
5. Tool approval records had no Session identity or history rollback boundary.
6. Protected payload content did not bind `session_id`.
7. Product Session service released Turns only on one uninterrupted Runner call and had no interrupted item-count update or rollback helper.
8. Session creation API accepted only the tool-free execution path.

## Immutable Reference findings

### `tests/test_hitl_session_scenario.py`

The official scenario calls:

```text
Runner.run(agent, message, session=session)
→ interruption
→ state.approve() or state.reject()
→ Runner.run(agent, state, session=session)
```

It covers multiple approved Turns and a rejected Turn, and asserts persisted function call/output identity.

### `tests/test_run_impl_resume_paths.py`

`test_resumed_approval_does_not_duplicate_session_items` runs the same Session on prepare and resume and asserts exactly one function-call item and one function-output item for the approval call ID.

### Adopt/adapt decision

Adopt:

- installed SDK Session argument on both initial and resumed Runner calls;
- SDK RunState approval/rejection;
- SDK duplicate-item protection.

Adapt in product code:

- immutable Session+approval policy;
- Product Session active-Turn lease held across interruption;
- Session identity in preflight/protected payload/approval ledger;
- safe canonical interrupted/complete Events;
- approved and rejected Turn commit semantics;
- failed partial-history rollback;
- operator inbox Session metadata;
- Runtime binding and Evaluation evidence.

Reject:

- direct Reference import;
- Session history in Product Event/SQLite;
- browser or model-selected Session database path;
- dynamic Tool/Agent creation;
- claiming distributed atomicity or process-loss resume not implemented.

## Implemented files

Core:

- `src/okcanvas_agent_runtime/sessions/approval_policy.py`
- `src/okcanvas_agent_runtime/sessions/service.py`
- `src/okcanvas_agent_runtime/tool_approval/gateway.py`
- `src/okcanvas_agent_runtime/tool_approval/service.py`
- `src/okcanvas_agent_runtime/tool_approval/store.py`
- `src/okcanvas_agent_runtime/tool_approval/models.py`
- `src/okcanvas_agent_runtime/protected_payload/models.py`
- `src/okcanvas_agent_runtime/protected_payload/store.py`
- `src/okcanvas_agent_runtime/run_submission/service.py`
- `src/okcanvas_agent_runtime/run_submission/execution.py`
- `src/okcanvas_agent_runtime/execution/runtime_binding.py`
- `src/okcanvas_agent_runtime/agent_definitions/catalog.py`
- `src/okcanvas_agent_runtime/control_api/app.py`
- `src/okcanvas_agent_runtime/control_api/contracts.py`

Specifications:

- `specs/runtime/sqlite-session-approval-policy.json`
- `specs/agents/session-approval-agent/*`
- `specs/evaluations/sqlite-session-approval-v1/case.json`

Tests and acceptance:

- `tests/test_sqlite_session_approval_composition.py`
- STEP046 additions to Agent Definition, Runtime binding, Session and protected-payload tests;
- `scripts/run_step046_acceptance.py`
- `sh_run_step046_acceptance.cmd`.

## Important implementation result

The existing P0 walking-skeleton catalog remains exactly ten scenarios. STEP046 is a P1 composition available through the existing Agent catalog, Session controls and separate Approval Operator. It does not mutate the P0 completion proof or introduce a second execution engine.
