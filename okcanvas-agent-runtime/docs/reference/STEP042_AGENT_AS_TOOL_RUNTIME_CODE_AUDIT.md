# STEP042 — Agent-as-Tool Runtime code audit

## Audited product paths

- `src/okcanvas_agent_runtime/agent_definitions/catalog.py`
- `src/okcanvas_agent_runtime/execution/runtime_binding.py`
- `src/okcanvas_agent_runtime/execution/openai_gateway.py`
- `src/okcanvas_agent_runtime/execution/service.py`
- `src/okcanvas_agent_runtime/invocations/service.py`
- `src/okcanvas_agent_runtime/streaming/adapter.py`
- `src/okcanvas_agent_runtime/streaming/broker.py`
- `src/okcanvas_agent_runtime/run_submission/service.py`
- `specs/runtime/sub-agent-invocation-policy.json`
- `specs/runtime/agent-as-tool-policy.json`

## Audited upstream paths

Primary installed-SDK answer key:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/agent.py:550-949`
  - `Agent.as_tool()`;
  - nested streamed/non-streamed Runner selection;
  - `on_stream` callback;
  - explicit `run_config` handling;
  - fallback to `ToolContext.run_config` when omitted;
  - custom output extraction.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tool_context.py`
  - Tool invocation context and parent RunConfig access.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run.py`
  - cumulative usage and nested Runner behavior.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/stream_events.py`
  - streamed nested Agent event classes.
- `reference/upstream/openai-agents-python-0.19.0/tests/test_agent_as_tool.py`
  - Agent Tool construction, custom output and nested execution expectations.

Executable application code imports the installed `agents` dependency only. No `/reference` module is imported.

## Confirmed upstream behavior

1. `Agent.as_tool()` returns a Function Tool backed by a nested Agent Runner.
2. The parent receives the nested Agent result and may continue its own run.
3. Nested streaming is delivered through `on_stream`.
4. When `run_config` is omitted and Tool context exists, the parent ToolContext RunConfig may be reused.
5. `custom_output_extractor` controls the value returned from the nested result to the parent.
6. SDK usage is cumulative in the shared run context; the SDK does not create product invocation rows or split product usage.

## Product gap before STEP042

STEP040 could describe an `AGENT_AS_TOOL` edge and allocate an identity, but no child Agent ran. STEP041 implemented control transfer, not delegation with parent resumption. Connecting `Agent.as_tool()` directly would have caused:

- no product-owned child invocation lifecycle;
- implicit parent RunConfig inheritance unless overridden;
- no bounded child result contract;
- no deterministic child/parent usage partition;
- raw nested events potentially reaching the browser adapter;
- no canonical safe start/completion evidence;
- no proof that parent control returned;
- ambiguous workspace inheritance.

## Adopted

- installed SDK `Agent.as_tool()`;
- streamed nested Runner and `on_stream` callback;
- `custom_output_extractor`;
- strict parent-owned declared child target;
- SDK cumulative usage as the source for deterministic delta accounting.

## Adapted

- explicit child RunConfig instead of ToolContext fallback;
- STEP040 invocation ledger for child identity/state;
- bounded structured JSON result normalization;
- product-owned safe nested-stream adapter;
- canonical `agent.tool.started/completed` evidence;
- usage partition into child delta and parent remainder;
- no workspace for language-only parent/child;
- Runtime binding over policy, graph and implementation.

## Rejected for V1

- implicit parent RunConfig inheritance;
- dynamic child selection or plugin loading;
- multiple/nested Agent Tool calls;
- Agent-as-Tool mixed with Handoff, MCP, local Tool, approval or Session;
- raw child inputs/results and SDK objects in Events or DB;
- second Product Task/Run for the nested child;
- physical workspace or Sandbox allocation;
- failure fallback that converts nested execution failure into an apparently successful Tool result.

## Code-derived lifecycle conclusion

The correct product model is not a Handoff. ROOT remains `RUNNING`; one child invocation becomes `RUNNING` during the nested call; child usage is the cumulative delta; after the child succeeds ROOT resumes and receives the remaining total usage. This is implemented in the shared invocation ledger rather than a second Agent Tool ledger.

## Acceptance conclusion

The deterministic acceptance proves actual parent→nested child→parent control flow, explicit child configuration, safe nested streaming, exact usage partition, one Product Run, bounded result, verified Artifact/Evaluation, no workspace, no sensitive persistence, and unchanged Reference snapshots.
