# OR-ISSUE-030 — Monolithic pytest runner had no bounded, checkpointed evidence

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

A single `python -m pytest -q` invocation did not complete within the available execution bound. A verbose diagnostic run reached the real-repository STEP060 inspection test after hundreds of successful tests but still produced no final suite result. The same 225 files all passed when executed in bounded isolated groups.

## Code-confirmed root cause

The validation command used one unbounded interpreter process for all files. It had no per-file or per-group timeout, no checkpoint result, and no machine-readable partial evidence. Therefore any process-lifetime slowdown or leaked resource in one point of the historical suite invalidated the entire result even when every file was independently executable. The defect was in the regression harness contract: it could neither bound nor localize a stalled group.

The exact internal cause of the monolithic-process slowdown is not asserted because the completed isolated evidence does not prove one. The recurrence fix deliberately addresses the confirmed harness deficiency rather than guessing at an unproven Product cause.

## Impact

The full regression could consume the entire validation window and leave no authoritative pass/fail record. Fresh-ZIP validation would be non-repeatable, and another conversation could not identify which files had actually completed.

## Fix

Added `scripts/run_step081_python_regression.py`:

- freezes the sorted `tests/test_*.py` inventory;
- runs 20 files per fresh Python process;
- applies a 300-second bound to every group;
- writes one log per group, machine-readable JUnit-derived counts, and an atomic checkpoint after every group;
- resumes from the checkpoint and aggregates all files into one STEP081 regression JSON;
- fails on a timeout, failure, error, or missing group result.

## Detailed evidence

The canonical run covers 225 test files in 12 groups and reports:

```text
896 passed
0 failed
0 errors
0 skipped
```

## Recurrence-prevention gate

STEP081 deterministic and Fresh-ZIP validation invoke the bounded regression runner and require exact full-file coverage, zero timeout groups, zero failures/errors/skips, and the expected aggregate result.
