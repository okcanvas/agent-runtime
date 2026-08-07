# OR-ISSUE-107 — Ambiguous Organization Context structured output failed after Tool success

## Status

```text
FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_VALIDATION_IN_PROGRESS
Windows Live rerun: PENDING
```

## Proven failure

The actual STEP008R1 Windows Live run used `gpt-4.1`. All four short expressions routed to the
Organization Context Session Root and called the expected Child MCP Tool. `김민수 정보` and
`김민수 직책` completed `resolve_organization_context` with two stable candidates, then failed in
Child structured output handling with `SDK_RUN_FAILED / ModelBehaviorError`. Single-entity resolve
and empty search completed.

## Code cause

`OrganizationContextReadResult` combined a strict provider JSON Schema with Pydantic cross-field
semantics. OpenAI strict JSON Schema cannot encode requirements such as "NEEDS_CLARIFICATION must
contain an operation and unverified candidates". A provider-schema-valid object could therefore be
rejected by Pydantic inside SDK output parsing before Product Agent-as-Tool normalization.

## Fix

- Structural field/type constraints remain in `OrganizationContextReadResult` and its JSON Schema.
- Cross-field Organization Context semantics are enforced after the Child run from the exactly one
  observed allowlisted MCP Tool result.
- Ambiguous resolve preserves every bounded stable candidate ID and deterministically emits
  `NEEDS_CLARIFICATION` with department/position evidence.
- No model retry and no Tool retry are added.
- Safe diagnostics retain only output contract, error category, field paths and error types. Raw
  model output, Tool arguments, Tool results and raw exception text are not persisted.

## Recurrence gates

```text
tests/test_step090_organization_context_ambiguous_result_normalization.py
tests/test_step088_organization_context_session_delegation.py
tests/test_step088r1_organization_context_bounded_response_diagnostics.py
scripts/run_step090_acceptance.py
Workspace STEP008R2 four-prompt Windows Live acceptance
```
