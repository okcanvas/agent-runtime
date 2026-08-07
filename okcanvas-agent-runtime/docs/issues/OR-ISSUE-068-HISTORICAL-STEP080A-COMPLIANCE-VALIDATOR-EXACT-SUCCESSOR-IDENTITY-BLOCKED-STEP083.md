# OR-ISSUE-068 — Historical STEP080A Compliance validator exact successor identity blocked STEP083

## Symptom

Full STEP083 regression failed because the retained STEP080A Compliance validator required the current Product to be exactly STEP082B / 2.62.2.

## Code-confirmed root cause

The historical validator mixed immutable STEP080A evidence validation with one transient current-successor identity. Its actual architectural requirement is that the Product has advanced beyond STEP080A through the STEP081 relocation boundary.

## Impact

STEP080A evidence remained intact, but every later valid cumulative Product revision would fail the historical validator.

## Correction

The validator now requires a non-STEP080A `STEP08*` Product at version 2.61.0 or later, while retaining exact STEP080A record identity, constitution hash, pending historical Windows gate and complete STEP081 relocation evidence.

## Recurrence gate

- `scripts/validate_step080a_compliance.py`;
- `tests/test_step080a_architecture_constitution_and_compliance_gates.py`;
- full STEP083 Python regression.
