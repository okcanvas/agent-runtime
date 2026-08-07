# Reference Code Map

## Audit baseline

- Full machine-readable inventory: `../docs/reference/STEP036A_REFERENCE_CAPABILITY_INVENTORY.json`
- Capability audit: `../docs/36-REFERENCE-WIDE-RUNTIME-CAPABILITY-AUDIT.md`
- Master plan: `../docs/plans/STEP036A_REFERENCE_WIDE_RUNTIME_CAPABILITY_MASTER_PLAN.md`

## Primary: OpenAI Agents Python 0.19.0

### Core Agent and Runner

- Agent composition: `upstream/openai-agents-python-0.19.0/src/agents/agent.py`
- Runner loop: `upstream/openai-agents-python-0.19.0/src/agents/run.py`
- RunState and interruptions: `upstream/openai-agents-python-0.19.0/src/agents/run_state.py`
- Results and items: `upstream/openai-agents-python-0.19.0/src/agents/result.py`, `items.py`
- Output schemas: `upstream/openai-agents-python-0.19.0/src/agents/agent_output.py`
- Hooks and usage: `upstream/openai-agents-python-0.19.0/src/agents/lifecycle.py`, `usage.py`
- Error handlers and model retry: `upstream/openai-agents-python-0.19.0/src/agents/run_error_handlers.py`, `retry.py`

### Streaming

- Stream event types: `upstream/openai-agents-python-0.19.0/src/agents/stream_events.py`
- Streaming Runner implementation: `upstream/openai-agents-python-0.19.0/src/agents/run_internal/streaming.py`
- Text and item examples: `upstream/openai-agents-python-0.19.0/examples/basic/stream_text.py`, `stream_items.py`
- Streaming tests: `upstream/openai-agents-python-0.19.0/tests/test_agent_runner_streamed.py`, `test_stream_events.py`, `test_streamed_terminal_output_backfill.py`

### Function Tools and Tool policy

- Tool contracts: `upstream/openai-agents-python-0.19.0/src/agents/tool.py`
- Tool decorator: `upstream/openai-agents-python-0.19.0/src/agents/decorators.py`
- Function schema: `upstream/openai-agents-python-0.19.0/src/agents/function_schema.py`
- Tool context: `upstream/openai-agents-python-0.19.0/src/agents/tool_context.py`
- Tool guardrails: `upstream/openai-agents-python-0.19.0/src/agents/tool_guardrails.py`
- Function Tool tests: `upstream/openai-agents-python-0.19.0/tests/test_function_tool.py`, `test_function_tool_decorator.py`, `test_tool_context.py`

### Handoffs and routing

- Handoff implementation: `upstream/openai-agents-python-0.19.0/src/agents/handoffs/`
- Prompt/filter helpers: `upstream/openai-agents-python-0.19.0/src/agents/extensions/handoff_prompt.py`, `handoff_filters.py`
- Routing example: `upstream/openai-agents-python-0.19.0/examples/agent_patterns/routing.py`
- Message-filter examples: `upstream/openai-agents-python-0.19.0/examples/handoffs/`
- Handoff tests: `upstream/openai-agents-python-0.19.0/tests/test_handoff_tool.py`, `test_handoff_history_duplication.py`, `test_handoff_prompt.py`

### Agents as Tools

- `Agent.as_tool()`: `upstream/openai-agents-python-0.19.0/src/agents/agent.py`
- Basic/structured/streaming examples: `upstream/openai-agents-python-0.19.0/examples/agent_patterns/agents_as_tools*.py`
- Tests: `upstream/openai-agents-python-0.19.0/tests/test_agent_as_tool.py`, `test_agent_tool_input.py`, `test_agent_tool_state.py`

### Sessions and conversation memory

- Session protocol: `upstream/openai-agents-python-0.19.0/src/agents/memory/session.py`
- SQLite Session: `upstream/openai-agents-python-0.19.0/src/agents/memory/sqlite_session.py`
- OpenAI Conversations and Responses compaction: `upstream/openai-agents-python-0.19.0/src/agents/memory/openai_conversations_session.py`, `openai_responses_compaction_session.py`
- Session persistence inside Runner: `upstream/openai-agents-python-0.19.0/src/agents/run_internal/session_persistence.py`
- Examples: `upstream/openai-agents-python-0.19.0/examples/memory/`
- Tests: `upstream/openai-agents-python-0.19.0/tests/memory/`, `test_hitl_session_scenario.py`, `test_run_impl_resume_paths.py`

### Guardrails

- Input/output Guardrails: `upstream/openai-agents-python-0.19.0/src/agents/guardrail.py`
- Tool Guardrails: `upstream/openai-agents-python-0.19.0/src/agents/tool_guardrails.py`
- Examples: `upstream/openai-agents-python-0.19.0/examples/agent_patterns/input_guardrails.py`, `output_guardrails.py`, `examples/basic/tool_guardrails.py`
- Tests: `upstream/openai-agents-python-0.19.0/tests/test_guardrails.py`, `test_tool_guardrails.py`, `test_output_guardrail_cancellation.py`

### MCP

- Server transports and lifecycle: `upstream/openai-agents-python-0.19.0/src/agents/mcp/server.py`
- Manager: `upstream/openai-agents-python-0.19.0/src/agents/mcp/manager.py`
- Tool conversion/filtering: `upstream/openai-agents-python-0.19.0/src/agents/mcp/util.py`
- Examples: `upstream/openai-agents-python-0.19.0/examples/mcp/`, `examples/hosted_mcp/`
- Tests: `upstream/openai-agents-python-0.19.0/tests/mcp/`

### Models, retries, and reasoning

- Model interfaces/providers: `upstream/openai-agents-python-0.19.0/src/agents/models/`
- Model settings: `upstream/openai-agents-python-0.19.0/src/agents/model_settings.py`
- Retry policy: `upstream/openai-agents-python-0.19.0/src/agents/retry.py`
- Examples: `upstream/openai-agents-python-0.19.0/examples/model_providers/`, `examples/reasoning_content/`
- Tests: `upstream/openai-agents-python-0.19.0/tests/models/`

### Hosted Tools

- Tool implementations: `upstream/openai-agents-python-0.19.0/src/agents/tool.py`
- Examples: `upstream/openai-agents-python-0.19.0/examples/tools/`
- Includes Web Search, File Search, Code Interpreter, Image Generation, Computer Use, Shell, Apply Patch, Tool Search, Programmatic Tool Calling, and Codex.

### Sandbox and experimental Codex

- Sandbox Runtime: `upstream/openai-agents-python-0.19.0/src/agents/sandbox/`
- Sandbox examples: `upstream/openai-agents-python-0.19.0/examples/sandbox/`
- Sandbox tests: `upstream/openai-agents-python-0.19.0/tests/sandbox/`
- Experimental Codex: `upstream/openai-agents-python-0.19.0/src/agents/extensions/experimental/codex/`
- Codex examples: `upstream/openai-agents-python-0.19.0/examples/tools/codex.py`, `codex_same_thread.py`
- Repository review example: `upstream/openai-agents-python-0.19.0/examples/sandbox/tutorials/repo_code_review/main.py`

### Realtime and voice

- Realtime Runtime: `upstream/openai-agents-python-0.19.0/src/agents/realtime/`
- Realtime examples/tests: `upstream/openai-agents-python-0.19.0/examples/realtime/`, `tests/realtime/`
- Voice pipeline: `upstream/openai-agents-python-0.19.0/src/agents/voice/`
- Voice examples/tests: `upstream/openai-agents-python-0.19.0/examples/voice/`, `tests/voice/`

## Temporal durability example

- Worker/plugin configuration: `upstream/temporal-openai-agents-demos/openai_agents/run_worker.py`
- Interactive workflow: `upstream/temporal-openai-agents-demos/openai_agents/workflows/interactive_research_workflow.py`
- Research manager: `upstream/temporal-openai-agents-demos/openai_agents/workflows/research_agents/research_manager.py`
- Use only as a later distributed-workflow reference. Temporal retry is not the OKCanvas governed replay policy.

## Customer-service UX and Handoff example

- Agent graph: `upstream/openai-cs-agents-demo/python-backend/airline/agents.py`
- Guardrails: `upstream/openai-cs-agents-demo/python-backend/airline/guardrails.py`
- Tools and context mutation: `upstream/openai-cs-agents-demo/python-backend/airline/tools.py`
- ChatKit server: `upstream/openai-cs-agents-demo/python-backend/server.py`
- Demo in-memory store: `upstream/openai-cs-agents-demo/python-backend/memory_store.py`
- UI event panel: `upstream/openai-cs-agents-demo/ui/components/chatkit-panel.tsx`
- Adapt UX and graph visibility only; do not adopt demo persistence.

## Streaming API adapter example

- FastAPI entry: `upstream/openai-agents-streaming-api/src/api/main.py`
- Router adapter: `upstream/openai-agents-streaming-api/src/api/utils/agent_router.py`
- Session helper: `upstream/openai-agents-streaming-api/src/api/utils/session_utils.py`
- Research manager: `upstream/openai-agents-streaming-api/src/research_bot/manager.py`
- Deep research Agent-as-Tool orchestrator: `upstream/openai-agents-streaming-api/src/deep_research_agent/orchestrator.py`
- Adapt event formatting and endpoint ergonomics only; do not adopt broad exception handling or implicit session defaults.
