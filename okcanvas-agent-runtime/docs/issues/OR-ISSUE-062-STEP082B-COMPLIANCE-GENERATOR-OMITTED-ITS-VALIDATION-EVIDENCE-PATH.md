# OR-ISSUE-062 — STEP082B Compliance generator omitted its validation evidence path

## Symptom

The first STEP082B Compliance validation passed 14/15. The actual changed-file inventory contained `docs/evidence/STEP082B_COMPLIANCE_VALIDATION.json`, while the generated Compliance record did not declare that path.

## Code-confirmed root cause

The generator predeclared only its own Compliance record output. The validator was redirected to a Product evidence path, which existed before inventory comparison and therefore correctly entered the actual changed-file set.

## Impact

Constitution traceability was incomplete by one generated evidence path. No gate, clause or Product behavior failed.

## Correction

The generator now predeclares both the Compliance record and its canonical validation evidence output before computing the self hash and traceability coverage.

## Recurrence gate

- exact changed-file equality in `validate_step082b_compliance.py`;
- zero unregistered/stale changed files;
- Fresh final Compliance rerun.
