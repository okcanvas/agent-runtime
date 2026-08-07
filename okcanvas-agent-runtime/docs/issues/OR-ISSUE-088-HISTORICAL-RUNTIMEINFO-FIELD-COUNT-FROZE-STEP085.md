# OR-ISSUE-088 — Historical RuntimeInfo field-count tests froze the STEP085 total

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`

## Discovered in

`STEP086_GROUPWARE_READ_ONLY_VERTICAL`

## Failure

STEP086 added thirteen declared RuntimeInfo fields, moving the actual dataclass total from 877 to 890. Two retained tests still required the literal STEP085 count and rejected the additive current schema.

## Root cause

The architecture validator already had a current-field-count SOT, but historical tests duplicated the numeric value instead of importing that SOT.

## Correction

- `scripts/step081_architecture.py.EXPECTED_RUNTIME_INFO_FIELDS` is a current-baseline SOT and is now 910 for STEP086R1; historical validators must not freeze their own copy.
- Retained tests derive the expected count from that constant.
- The architecture validator continues to compare the real dataclass field count with the current SOT.

## Recurrence gate

- `scripts/validate_step081_architecture.py`
- `tests/test_step081_root_package_and_architecture_restructuring.py`
- `tests/test_step082b_coding_execution_plane_and_distribution_boundary.py`
