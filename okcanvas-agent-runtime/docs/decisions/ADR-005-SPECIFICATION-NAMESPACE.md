# ADR-005 — Specification namespace

## Status
Accepted on 2026-07-28.

## Decision
Move root declarative directories from `/agents`, `/mcp`, and `/tools` to:

```text
/specs/agents
/specs/mcp
/specs/tools
```

## Reason
The official OpenAI Agents SDK imports from the top-level Python package `agents`, and MCP implementations commonly import from `mcp`. Root directories with those names can become PEP 420 namespace packages even without `__init__.py`, confusing readiness checks and developers.

`specs/` also describes the content more accurately: the files include schemas, policies, instructions, and evaluation cases, not only prose documentation.

## Consequences
- executable code remains under `src/okcanvas_agent_runtime/`;
- root Python packages named `agents` or `mcp` are forbidden;
- specification directories contain no `__init__.py`;
- tests verify that the old root directories do not return.
