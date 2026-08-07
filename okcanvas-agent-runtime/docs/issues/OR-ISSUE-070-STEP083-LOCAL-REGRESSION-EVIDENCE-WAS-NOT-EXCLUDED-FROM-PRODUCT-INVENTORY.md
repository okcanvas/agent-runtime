# OR-ISSUE-070 — STEP083 local regression evidence was not excluded from Product inventory

## Symptom

The STEP083 Python checkpoint runner wrote logs under `docs/evidence/step083-local/`, but the shared Product inventory exclusion policy and `.gitignore` ended at `step082b-local`.

## Code-confirmed root cause

Creating the new STEP-specific runner did not extend the centralized machine-local evidence prefixes. `package_source.py` delegates inclusion to that policy, so the logs were eligible for the candidate ZIP.

## Impact

Machine-local checkpoint logs could enter the immutable Product archive and exact changed-file Compliance set, making packaging host-dependent.

## Correction

`step083-local` is now excluded by `included_relative_path` and `.gitignore`. The canonical aggregate `STEP083_PYTHON_REGRESSION.json` remains Product evidence.

## Recurrence gate

- `test_step083_local_evidence_is_excluded_from_product_inventory`;
- Product inventory and final ZIP forbidden-entry checks;
- STEP083 Compliance exact changed-file validation.
