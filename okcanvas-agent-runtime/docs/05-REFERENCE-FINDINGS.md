# Reference Findings Baseline

These findings were derived from the supplied source snapshots. They are navigation guidance, not a replacement for reading the exact code before a future implementation decision.

## openai-agents-python 0.19.0

Primary implementation reference. Relevant areas include:

- `src/agents/agent.py`: Agent definition and tool/handoff/guardrail configuration.
- `src/agents/run.py`: Runner execution loop.
- `src/agents/run_state.py`: interruption approval/rejection and JSON serialization.
- `src/agents/memory/`: session abstractions and implementations.
- `src/agents/mcp/`: MCP integration.
- `src/agents/sandbox/`: filesystem, shell, Docker/Unix sandbox, snapshots, skills, and memory.
- `src/agents/extensions/experimental/codex/`: experimental Codex CLI integration.
- `src/agents/extensions/experimental/codex/exec.py`: actual `codex exec --experimental-json` subprocess assembly. When `CodexOptions.env` is omitted it copies the full parent environment; STEP002 therefore supplies an explicit allowlist. The `network_access_enabled` option is written to `sandbox_workspace_write.network_access`, so the supplied SDK source alone does not prove effective arbitrary-command network denial for `sandbox_mode=read-only`.
- `examples/tools/codex.py` and `codex_same_thread.py`: Codex as an Agent tool and thread reuse.

Decision: use the published SDK as a pinned dependency in a later STEP; do not import the reference tree directly.

## Temporal OpenAI Agents demos

Demonstrates wrapping Agent runs and model/tool operations in Temporal workflows and activities. Useful for durability research, but the supplied snapshot is demo-grade and targets an older Agents SDK range. It is not the initial runtime base.

## OpenAI customer-service Agents demo

Demonstrates multiple specialized Agents, handoffs, ChatKit integration, and context mutation. State is memory-backed and operational authentication, durable ownership, production approval, and complete testing are not established by the supplied code.

## OpenAI Agents streaming API example

Demonstrates a generic FastAPI router shape for synchronous and SSE Agent calls plus a simple planner/search/writer research flow. The supplied code contains incompatible or unsafe patterns, including API-key initialization confusion, open session access, broad CORS, HTTP-200 error bodies, and disconnected deep-research code. Use only as an adapter/negative reference.
