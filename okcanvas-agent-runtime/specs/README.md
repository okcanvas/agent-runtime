# Declarative Specifications

This tree contains product contracts and is intentionally separate from executable Python packages.

- `agents/`: Agent instructions, schemas, policy, and evaluation assets.
- `tools/`: Tool declarations and safety policy.
- `mcp/`: future MCP contracts and deny-by-default policy.
- `runtime/`: product Task, Run, Event, Approval, Artifact, and Validation contracts not supplied by the SDK.

Do not add `__init__.py` files here. Runtime implementations belong under `src/okcanvas_agent_runtime/`.


STEP043 adds `specs/runtime/sqlite-session-policy.json`, one `session-continuity-agent`, and one compatible Evaluation Case. Session policy, Agent Definition, Runtime implementation, and execution path are confirmation-bound.

## STEP046 composition specification

`runtime/sqlite-session-approval-policy.json` is the immutable policy for the one supported P1 composition: local SQLite Session plus exactly one `ALWAYS` Function Tool. It is Runtime-bound and does not authorize other mixed capability graphs.

## STEP048 closed composition

`session-guardrail-language-agent` is the only Session+Agent-Guardrail graph authorized by STEP048. It is language-only, permits one INPUT and one OUTPUT Guardrail, and uses exact pre-Turn item-count rollback for every tripwire.
