# OR-ISSUE-091 — Final HANDOFF rewrite recurred preserved Skill omission

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`

## Discovered in

`STEP086_GROUPWARE_READ_ONLY_VERTICAL` final Fresh ZIP Python regression

## Failure

The source-tree Python regression had passed, but the final STEP086 `HANDOFF.md` was rewritten afterwards and no longer named the retained `document-review-v1` Product Skill. The immutable Fresh ZIP then failed `test_step070_skill_runtime_is_present_and_service_visible` with 1 failure out of the first 770 executed tests.

## Root cause

This is a direct recurrence of OR-ISSUE-067 (and the earlier OR-ISSUE-057 pattern). The existing recurrence gate was a normal source regression assertion. It did not enforce either of the two finalization invariants:

1. no Product file may change after the full source regression without rerunning it;
2. the final Fresh ZIP validator must independently inspect cumulative HANDOFF identities.

Therefore a late documentation rewrite could invalidate ZIP-only continuation after the source regression evidence had already been recorded.

## Correction

- `HANDOFF.md` now has one explicit retained Product-owned capability identity section for `document-review-v1`, the four accepted Function Tools and `reference-catalog`.
- The existing STEP086 finalization regression checks those exact identities without increasing the cumulative test-file/test-count contract.
- `build_step086_fresh_validation_summary.py` now reads the extracted immutable HANDOFF and fails unless all retained identifiers are present.
- The full source regression, Compliance generation, packaging and full Fresh regression are rerun after this correction.

## Recurrence gate

- `tests/test_step086_groupware_read_only_vertical.py::test_step086_finalization_preserves_handoff_identities_and_excludes_local_evidence`
- `scripts/build_step086_fresh_validation_summary.py` check `handoff_retained_product_identities_exact`
- full source Python regression after final Product-file mutation
- final Fresh ZIP Python regression and final Fresh validation
