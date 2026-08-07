# OR-ISSUE-038 — STEP081 HANDOFF rewrite dropped a preserved Skill contract

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

Full regression failed `test_step070_skill_runtime_is_present_and_service_visible` because the new ZIP-only HANDOFF no longer mentioned the retained Product-owned `document-review-v1` Skill.

## Code-confirmed root cause

STEP081 replaced HANDOFF with a structure-focused document and omitted the preserved-capability section. Runtime and Skill code remained present; the failure was an incomplete handoff contract, not a removed feature.

## Impact

A new conversation using only the final ZIP could incorrectly conclude that the accepted Product-owned Skill foundation had been removed or was no longer part of the runtime baseline.

## Fix

HANDOFF now explicitly lists `document-review-v1` and the other major preserved runtime contracts, while stating that STEP081 grants no new Tool, WebSocket, model or filesystem authority.

## Recurrence-prevention gate

Historical STEP069/STEP070 contract tests and final Fresh-ZIP full regression must pass against the packaged HANDOFF.
