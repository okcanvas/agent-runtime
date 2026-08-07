# STEP036B — Sub-Agent invocation and workspace isolation code audit

## Scope

This audit refines the STEP036A capability order. It changes documentation and planning only. The audit was completed while the executable Runtime was STEP036 / 2.16.0. STEP036 is now
Windows live accepted. STEP037 implements the first governed Interactive Runner surface while the
sub-Agent isolation rules remain binding for STEP040 and later.

## Inspected current OKCanvas code

- `src/okcanvas_agent_runtime/agent_definitions/catalog.py`
- `src/okcanvas_agent_runtime/agent_definitions/models.py`
- `src/okcanvas_agent_runtime/execution/runtime_binding.py`
- `src/okcanvas_agent_runtime/execution/openai_gateway.py`
- `src/okcanvas_agent_runtime/workspace/**`
- current Codex read-only/write services and policies

Confirmed current behavior:

1. Agent definitions already live in independent `specs/agents/<agent-id>` directories.
2. The catalog rejects symbolic directories/files and path escape.
3. Generic execution currently supports no Handoff, no child invocation record, and no SDK Session.
4. Existing workspace code belongs to controlled Codex and Acceptance paths; it is not a generic
   parent/child workspace allocator.

## Inspected OpenAI Agents SDK code

- `src/agents/agent.py::Agent.as_tool`
- `src/agents/handoffs/__init__.py`
- `src/agents/run.py` and RunConfig behavior
- `src/agents/sandbox/**`
- `examples/agent_patterns/agents_as_tools*.py`
- `examples/agent_patterns/routing.py`
- `examples/handoffs/message_filter*.py`
- `examples/sandbox/tutorials/sandbox_resume/main.py`
- Sandbox and Agent-as-Tool tests from the STEP036A inventory

Confirmed SDK behavior:

1. Handoff changes the active Agent and transfers filtered Run history/items. It does not allocate a
   folder, Sandbox, Product child record, or new security boundary.
2. Agent-as-Tool invokes a nested Runner. When no nested RunConfig is supplied, it uses the parent
   Tool context's RunConfig. It deliberately separates approval context but does not automatically
   create a separate filesystem.
3. SDK Sandbox isolation is explicit. The caller creates a Sandbox client/session and passes the
   session through `SandboxRunConfig`.
4. A Sandbox session has its own Manifest, root, capabilities, mounts, snapshot, persistence, and
   resume lifecycle. These are too significant to infer automatically from “this is a sub-Agent.”

## Decision

Use three layers:

```text
Agent definition directory
→ child invocation/state namespace
→ physical workspace only when filesystem capability is granted
```

“Every sub-Agent always gets an independent folder” is too broad. The correct rule is:

- every sub-Agent definition is isolated;
- every child execution is invocation-isolated;
- every **file-capable** child execution is workspace-isolated;
- a language-only Agent gets no filesystem at all.

This is stricter than creating empty folders because absence of capability is stronger than an
unused directory.

## Plan correction

Insert `STEP040_SUB_AGENT_INVOCATION_SCOPE_FOUNDATION` before native Handoff and Agent-as-Tool.

The P0 sequence is now STEP037–STEP045. Native Handoff moves to STEP041, Agent-as-Tool to STEP042,
SQLite Session to STEP043, Guardrail to STEP044, and the integrated completion gate to STEP045.

The binding details are in
`docs/plans/STEP036B_SUB_AGENT_INVOCATION_AND_WORKSPACE_ISOLATION.md`.
