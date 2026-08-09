# Workspace R12 — Runtime STEP096B Grounded LLM Structured Delegation Admission Foundation

Current Workspace: WORKSPACE_STEP008R4R12_RUNTIME_STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION
Workspace Version: 0.8.4-r12
Current Runtime: STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION
Runtime Version: 2.80.0

State: LOCAL_DETERMINISTIC_ACCEPTED_LIVE_NOT_RUN
Promotion: CANDIDATE_LOCAL_DETERMINISTIC_ACCEPTED_LIVE_NOT_RUN

## Parent

- Parent Workspace: `WORKSPACE_STEP008R4R11_RUNTIME_STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION` / `0.8.4-r11`
- Parent package SHA-256: `656c74ec5a680a91a8561756e5fe3529d98785d42aa1cd5e417261bafd44ab8d`
- R10E/R10ER1 STEP094R2 Windows-focused Live evidence remains historical accepted evidence and is not rewritten.

## Product change

Runtime advances to STEP096B/2.80.0. Connector Product source is unchanged.

STEP096B keeps STEP096A's Context Enrichment Plane and changes only the bound unified Session Root
execution contract. The Root LLM may answer directly or request exactly one of the two existing
read-only specialist Agents with a structured schema. Runtime admission validates the request before
nested execution, injects stable IDs only from server-owned SessionContextFocus, chooses the exact
MCP Tool, and lazy-connects only the admitted child's MCP.

The model has no stable-ID or Tool-name input fields. Product-owned non-read side-effect fences cannot
be downgraded to read delegation. A denied specialist request cannot fall back to the other child in
the same Turn. Root direct MCP remains forbidden.

## Acceptance

- Runtime STEP096B static: 20/20 PASS.
- Runtime focused regression: 63/63 PASS.
- Runtime deterministic acceptance: 6/6 PASS.
- acceptance launcher registry: 7/7 PASS.
- architecture constitution: 16/16 PASS.
- current architecture successor checks are exact; historical STEP081 identity is intentionally different.
- STEP096B Windows/OpenAI Live: NOT RUN.

The local analysis interpreter does not contain the `agents` package, therefore actual SDK execution
is not claimed. Pinned retained OpenAI Agents SDK 0.19.0 source contract was inspected.

## Next gate

Focused Windows/OpenAI Live acceptance of the real structured Root->child SDK path is required before
promoting STEP096B or expanding into unresolved multi-stage relations, compound multi-child execution,
or write capabilities. STEP095A durable-memory audit remains separate backlog.
