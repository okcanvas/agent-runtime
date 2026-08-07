# STEP041 — Native Handoff Runtime code audit

## Audited local code

- `src/okcanvas_agent_runtime/agent_definitions/`
- `src/okcanvas_agent_runtime/execution/openai_gateway.py`
- `src/okcanvas_agent_runtime/execution/service.py`
- `src/okcanvas_agent_runtime/execution/runtime_binding.py`
- `src/okcanvas_agent_runtime/invocations/service.py`
- `src/okcanvas_agent_runtime/invocations/store.py`
- `src/okcanvas_agent_runtime/persistence/sqlite_store.py`
- `src/okcanvas_agent_runtime/run_submission/service.py`
- `src/okcanvas_agent_runtime/streaming/`
- `specs/runtime/sub-agent-invocation-policy.json`
- `docs/plans/STEP040_SUB_AGENT_INVOCATION_SCOPE_FOUNDATION.md`

## Audited retained Reference

- `reference/upstream/openai-agents-python-0.19.0/src/agents/handoffs/__init__.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/handoffs/history.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/extensions/handoff_filters.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/lifecycle.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/result.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run.py`
- `reference/upstream/openai-agents-python-0.19.0/examples/agent_patterns/routing.py`
- `reference/upstream/openai-agents-python-0.19.0/examples/handoffs/message_filter.py`
- `reference/upstream/openai-agents-python-0.19.0/examples/handoffs/message_filter_streaming.py`
- `reference/upstream/openai-agents-python-0.19.0/tests/test_handoff_tool.py`
- `reference/upstream/openai-agents-python-0.19.0/tests/test_handoff_history_duplication.py`

## Confirmed upstream behavior

1. Native Handoff is represented to the model as an SDK Tool whose destination Agent object is captured by application code.
2. `handoff()` supports an input filter and `nest_handoff_history`; neither option creates a product invocation or filesystem workspace.
3. `remove_all_tools` removes Tool-related Run items from Handoff input but does not by itself define product persistence policy.
4. `RunHooks.on_handoff(context, from_agent, to_agent)` is the exact transition hook and exposes cumulative Run usage through the context wrapper.
5. `Runner.run_streamed()` emits `agent_updated_stream_event` after an Agent transition.
6. SDK result usage is cumulative for the complete Runner execution; the SDK does not partition it into OKCanvas parent and child invocation rows.
7. Handoff remains one Runner execution and does not imply a second Product Task or Run.

## Adopted

- installed SDK `handoff()`;
- official `remove_all_tools` input filter;
- `nest_handoff_history=False`;
- lifecycle `on_handoff` callback;
- streamed Agent update;
- one Runner execution across parent and child.

## Adapted

- SDK Agent objects are mapped back to immutable product Agent-definition IDs;
- Handoff callback creates and starts one Product child invocation;
- cumulative usage at the callback closes parent usage;
- final cumulative usage minus parent usage attributes child usage;
- SDK Agent update is enriched with safe product Agent ID;
- canonical `agent.handoff` stores identity/policy evidence only;
- Handoff policy and implementation are included in Runtime binding.

## Rejected or deferred

- model-selected arbitrary destination Agent;
- dynamic Handoff graph construction;
- raw Handoff input/history persistence;
- Handoff input payload;
- nested history;
- multiple/chained Handoffs;
- Handoff mixed with Tool, MCP, Agent-as-Tool, Session, approval, or workspace;
- treating Agent display name as invocation identity;
- directly importing executable Reference code.

## Local defect closed

STEP040 could prove a closed graph and create planned identities, but generic execution rejected every Handoff. The SDK transition also had no product-owned child lifecycle or usage partition. STEP041 closes exactly that gap for one sequential language-only Handoff while retaining one Product Task/Run and no physical workspace.

## Remaining risks

- Process loss after the SDK transition cannot resume the in-memory Runner at the child boundary.
- V1 usage partition depends on one sequential Handoff and cumulative usage monotonicity.
- Child-specific Artifact ownership and Evaluation are not yet modeled.
- Multiple/chained Handoffs require a separately audited transition and recovery policy.
