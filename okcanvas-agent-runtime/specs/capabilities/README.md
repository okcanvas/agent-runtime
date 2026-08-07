# Product-owned Capability Topology

This directory defines the structure used to normalize every Agent extension surface without
activating new authority.

Core families:

- `tool` — Function Tools and hosted Tools;
- `skill` — Product-owned instruction/static-resource packages;
- `sub-agent` — native Handoffs, Agent-as-Tool children, and Product orchestration children;
- `mcp` — declarative MCP servers;
- `guardrail` — Agent and Tool guardrails;
- `workspace` — Product-owned workspace bindings;
- `input` — bounded input adapters;
- `session` — explicit Session bindings.

`tool-discovery-policy.json` is **structure-only** in STEP080. It records future Tool Search
namespace hints, supported SDK surfaces, and direct/programmatic caller policy, while keeping
`ToolSearchTool`, deferred loading, and `ProgrammaticToolCallingTool` disabled.

The SDK example inventory below `examples/` binds conclusions to exact source files and SHA-256
values from the pinned `reference/upstream/openai-agents-python-0.19.0` tree. Upstream code is read
for audit only and is never imported by Product Runtime code.
