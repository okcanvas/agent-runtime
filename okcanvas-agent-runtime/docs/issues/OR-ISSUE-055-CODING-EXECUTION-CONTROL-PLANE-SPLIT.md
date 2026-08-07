# OR-ISSUE-055 — Coding execution authority was split across three control-plane families

## Symptom

The repository contained:

1. `AgentRuntimeService` with a fixed language-only `coding-agent` envelope;
2. `GenericAgentExecutionService` with Product Task/Run/Event/Artifact, Tool, MCP, Session and orchestration contracts;
3. Codex read/write/approval services exposed through the development CLI but absent from the generic Agent/Tool catalogs.

## Code-confirmed root cause

Capabilities were accumulated by successive vertical slices without one explicit Product execution-plane policy. The Product API already used the Generic service, but no machine gate prohibited legacy or Codex services from entering Product transports later.

## Impact

Adding a new Coding Agent could create a fourth execution path, duplicate approval/evidence semantics, and make product authority ambiguous.

## Correction

STEP082B declares `generic-agent-runtime` as the only Product control plane. Legacy language and Codex services remain available only as Developer-only compatibility/experimental planes until a later migration maps their behavior into Product capabilities.

## Recurrence gate

- `specs/runtime/product-execution-plane-policy.json`
- `scripts/validate_step082b_execution_plane.py`
- Product bootstrap/transport static import gate
- exact retained Agent/Tool catalog counts 27/4.
