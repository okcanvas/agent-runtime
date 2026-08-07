# OR-ISSUE-090 — STEP086 local evidence was not excluded from Product inventory

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`

## Discovered in

`STEP086_GROUPWARE_READ_ONLY_VERTICAL`

## Failure

The first STEP086 bounded Python runner targeted a STEP086 evidence path, but the Product inventory exclusions and `.gitignore` ended at STEP085. Running the validator would therefore make machine-local checkpoint logs appear as Product source changes.

## Root cause

Each step introduced a new local evidence directory while the inventory policy used a manually extended exact prefix list. The STEP086 runner was copied before the matching exclusion was registered.

## Correction

- The runner now writes under `docs/evidence/step086-local/`.
- The Product inventory excludes that prefix.
- `.gitignore` excludes the same path.
- A STEP086 regression verifies all three contracts.

## Recurrence gate

- `tests/test_step086_groupware_read_only_vertical.py::test_step086_local_evidence_is_excluded_from_product_inventory`
- `scripts/step081_product_inventory.py`
- STEP086 Compliance changed-file equality
