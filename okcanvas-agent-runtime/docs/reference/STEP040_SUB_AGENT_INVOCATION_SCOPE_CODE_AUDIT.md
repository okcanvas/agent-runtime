# STEP040 — Sub-Agent Invocation Scope code audit

## Audited local code

- `src/okcanvas_agent_runtime/agent_definitions/models.py`
- `src/okcanvas_agent_runtime/agent_definitions/catalog.py`
- `src/okcanvas_agent_runtime/execution/runtime_binding.py`
- `src/okcanvas_agent_runtime/execution/service.py`
- `src/okcanvas_agent_runtime/tool_approval/service.py`
- `src/okcanvas_agent_runtime/persistence/sqlite_store.py`
- `src/okcanvas_agent_runtime/product/models.py`
- `src/okcanvas_agent_runtime/control_api/app.py`
- `docs/plans/STEP036B_SUB_AGENT_INVOCATION_AND_WORKSPACE_ISOLATION.md`

## Audited retained Reference

- `reference/upstream/openai-agents-python-0.19.0/src/agents/handoffs/__init__.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/handoffs/history.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/agent.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tool_context.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_config.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/runtime_session_manager.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/session/`
- `reference/upstream/openai-agents-python-0.19.0/examples/handoffs/`
- `reference/upstream/openai-agents-python-0.19.0/tests/test_handoff_tool.py`
- `reference/upstream/openai-agents-python-0.19.0/tests/test_handoff_history_duplication.py`

## Confirmed upstream behavior

1. `HandoffInputData` carries input history, pre-Handoff items, new items, optional filtered input items, and Run context. It carries no product invocation ID and no filesystem lease.
2. Handoff targets are represented to the model as Tools, but the SDK destination remains an Agent object captured by product/application code.
3. `Agent.as_tool()` performs a nested Runner call. When no nested `run_config` is supplied, it can inherit `ToolContext.run_config`.
4. The SDK creates a fresh `ToolContext` for nested Agent-as-Tool approval state, but this is not an OKCanvas Product invocation ledger.
5. Sandbox materialization/session management is explicit and separate. Handoff or Agent-as-Tool alone does not allocate an isolated folder.

## Adopted

- closed child Agent definitions;
- different Handoff and Agent-as-Tool kinds;
- explicit parent/root identity before executing either SDK primitive;
- bounded graph depth and child counts;
- separate invocation usage/state scope;
- explicit workspace policy independent of Handoff semantics.

## Adapted

- SDK Agent graph becomes an immutable product definition graph and Runtime-binding input;
- SDK nested execution becomes a future child invocation under one Product Run;
- workspace is allocated only for file-capable invocations, not every language-only child;
- current root executions are recorded immediately so STEP041/042 do not introduce a second incompatible ledger.

## Rejected or deferred

- dynamic model-selected child Agent IDs;
- filesystem path supplied by prompt, model, Tool arguments, or Agent name;
- automatic parent writable-workspace inheritance;
- treating host directory separation as secure code isolation;
- Handoff/nested execution in STEP040;
- general Sandbox/provider implementation before a file-capable use case exists.

## Local defect closed

Before STEP040, `AgentDefinition` exposed `handoffs` but generic execution only recorded a literal `handoff_count=0`; there was no immutable child graph verification, invocation entity, parent relationship, child namespace, workspace policy, or child usage attribution shape. STEP040 closes that foundation without claiming native Handoff support.
