# OR-ISSUE-031 — STEP081 Acceptance called a nonexistent ReferenceVerification serializer

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

The STEP081 non-Python validation completed all four Reference integrity checks, but the integrated deterministic Acceptance could not write its result payload because it executed:

```text
ReferenceVerification.to_public_dict()
```

`ReferenceVerification` exposes `to_dict()` and has never defined `to_public_dict()`.

## Code-confirmed root cause

`scripts/run_step081_acceptance.py` was assembled from several evidence producers with different serialization APIs. The Reference catalog model in `okcanvas_agent_runtime/adapters/reference_catalog/models.py` defines the exact method `to_dict()`, while the new Acceptance script guessed a different method name. The earlier standalone non-Python helper used `dataclasses.asdict`, so it verified the underlying Reference content without exercising the integrated Acceptance serialization line.

## Impact

All Product, Node, and Reference checks could pass while STEP081 deterministic Acceptance still terminated with `AttributeError` during evidence construction. No authoritative `STEP081_ACCEPTANCE.json` could be produced, and Fresh-ZIP validation would repeat the same failure.

## Fix

The integrated Acceptance now calls the model-owned `ReferenceVerification.to_dict()` method. A focused executable regression verifies all four Reference records serialize successfully and rejects reintroduction of `to_public_dict` in the STEP081 Acceptance source.

## Detailed evidence

```text
Reference records: 4
verified: 4/4
serialization method: to_dict
focused regression: PASS
```

## Recurrence-prevention gate

`tests/test_step081_root_package_and_architecture_restructuring.py::test_step081_acceptance_reference_verification_serialization_contract` executes the real Reference verification objects and serializes them through the same model contract used by STEP081 Acceptance. Final deterministic and Fresh-ZIP Acceptance must also complete and emit `STEP081_ACCEPTANCE.json`.
