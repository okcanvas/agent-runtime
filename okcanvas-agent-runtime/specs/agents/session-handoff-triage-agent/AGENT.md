# SQLite Session Handoff Triage Agent

STEP047 root Agent. It owns one Product SQLite Session and may transfer each governed Turn exactly once
to the immutable `handoff-specialist-agent`. The Turn lease remains held through terminal child completion.
It has no Tool, MCP, Agent-as-Tool, Guardrail, or workspace capability.
