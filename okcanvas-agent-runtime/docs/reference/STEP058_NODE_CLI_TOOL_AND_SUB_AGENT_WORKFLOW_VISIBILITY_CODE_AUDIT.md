# STEP058 Code and Reference Audit

## Current-product findings

- `clients/okcanvas-agent-cli/src/render.ts:isCliCompatible` previously rejected every Agent declaring a Tool, MCP server, Handoff, Agent Tool or Guardrail.
- The Control API already exposes safe `tool_capabilities`, `handoffs` and `agent_tools` in Agent summaries.
- `src/okcanvas_agent_runtime/execution/openai_gateway.py` already emits safe `tool.started`, `tool.completed`, `agent.handoff`, `agent.tool.started` and `agent.tool.completed` lifecycle events.
- `src/okcanvas_agent_runtime/execution/service.py` already builds Product-owned ROOT, HANDOFF and AGENT_AS_TOOL invocation records and partitions usage.
- STEP038, STEP041, STEP042, STEP047 and STEP049 already accepted the underlying execution paths. No new Runtime graph was required.

## Immutable Reference findings

Consulted:

- `reference/CODE_MAP.md` and `reference/MANIFEST.json`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tool.py`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/handoffs/`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/agent.py` (`Agent.as_tool`);
- streaming examples and tests listed in `reference/CODE_MAP.md`.

Adopted only the UX distinction between Tool lifecycle, control transfer through Handoff and parent-retained Agent-as-Tool calls. Product execution, policy, persistence and invocation authority remain in the existing OKCanvas Runtime. No Reference code was imported or modified.

## Selected boundary

The CLI accepts one isolated capability family only. A Function Tool must be public-catalogued as approval-free, read-only and without filesystem/network/Shell access. Handoff and Agent-as-Tool each permit exactly one declared child. Approval, MCP, Guardrail and mixed graphs remain deferred.
