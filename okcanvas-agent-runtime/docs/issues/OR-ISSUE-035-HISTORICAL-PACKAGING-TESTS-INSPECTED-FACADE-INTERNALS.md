# OR-ISSUE-035 — Historical packaging tests inspected facade implementation text

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

The current full regression failed two historical STEP072 tests although package exclusion behavior remained active. The tests required `"__pycache__"` and the STEP072B live-evidence tuple to occur literally inside `scripts/package_source.py`.

## Code-confirmed root cause

STEP081 centralized package inclusion policy in `scripts/step081_product_inventory.py`; `package_source.py` delegates to that policy. The tests verified the former facade's source layout rather than the canonical policy owner or produced ZIP behavior.

## Impact

A valid responsibility extraction was rejected and future refactors could be forced to duplicate policy strings in multiple files, recreating drift.

## Fix

The historical tests now inspect the canonical shared packaging policy. Existing direct ZIP behavior tests continue to prove that bytecode and local live evidence are excluded.

## Recurrence-prevention gate

STEP072A/STEP072B historical tests, STEP081 direct packaging regression, product-inventory exact diff, and Fresh-ZIP package validation must all pass.
