# WORKSPACE-ISSUE-034 — Ambiguous Organization Context result failed after successful MCP resolve

## Status

```text
FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_VALIDATION_IN_PROGRESS
Windows deterministic rerun: PENDING
Windows Live OpenAI rerun: PENDING
```

## Actual Windows evidence

STEP008R1 Live called `gpt-4.1`, the Organization Context Connector and the Node Example for all
four short expressions. Routing and the exact resolve/resolve/resolve/search Tool sequence were
observed. `김민수 정보` and `김민수 직책` failed only after the ambiguous resolve Tool completed,
with `SDK_RUN_FAILED / ModelBehaviorError`. `김선임 연락처` and `과장들 목록` succeeded.

## Code finding

`OrganizationContextReadResult` had Pydantic cross-field semantics that were not representable in
the provider strict JSON Schema. The SDK could accept the provider JSON and then fail Pydantic
validation before Product code could normalize the Child result.

## Closure

Runtime STEP090 moves ambiguity semantics to Product-owned post-Child normalization based on the
actual observed MCP result. STEP008R2 Live requires one normalization event per turn and requires
the two ambiguous turns to emit deterministic clarification metadata while preserving all stable
candidate IDs. Safe diagnostics expose only category, output contract, field paths and error types.
