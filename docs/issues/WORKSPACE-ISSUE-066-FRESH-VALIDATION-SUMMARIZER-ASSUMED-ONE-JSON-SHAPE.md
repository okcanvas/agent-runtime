# WORKSPACE-ISSUE-066 — Fresh validation summarizer assumed one JSON shape

## Status

FIXED_IN_R11_RELEASE_VALIDATION

## STEP

Workspace R11 / Runtime STEP096A

## Observation

All Fresh validators and the deterministic repack completed, but a final display-only summary script treated the STEP096A runner stdout `focused_pytest` string as if it were the persisted evidence object and raised `AttributeError`.

## Correction / recurrence gate

Final release validation now reads each validator output according to its own schema. Validation result aggregation must not rely on overlapping field names having identical JSON types.
