# OR-ISSUE-067 — STEP083 HANDOFF rewrite dropped preserved document-review Skill

## Symptom

Full regression failed because the rewritten STEP083 `HANDOFF.md` no longer named the existing Product-owned `document-review-v1` Skill.

## Code-confirmed root cause

The new HANDOFF focused on the Organization Assistant routing surface and summarized attachment review as a capability, but omitted the exact immutable Skill identifier required for ZIP-only continuation. This repeated the documentation-loss pattern previously recorded in OR-ISSUE-057.

## Impact

Product runtime behavior was unchanged, but a new conversation continuing from the ZIP could incorrectly infer that the Product Skill had been removed or replaced.

## Correction

HANDOFF now explicitly lists `document-review-v1`, all four retained Function Tools and the `reference-catalog` MCP allowlist.

## Recurrence gate

- `tests/test_step069_multi_user_service_client_contract_baseline.py`;
- full STEP083 Python regression;
- final Fresh ZIP HANDOFF inspection.
