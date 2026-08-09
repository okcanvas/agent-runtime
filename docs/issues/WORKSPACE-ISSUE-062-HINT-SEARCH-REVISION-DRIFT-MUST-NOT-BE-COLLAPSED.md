# WORKSPACE-ISSUE-062 — Hint Search Revision Drift Must Not Be Collapsed

## Status

FIXED_IN_STEP096A

## STEP

STEP096A

## Observation

Independent entity/term hint searches can observe different catalog revisions; choosing max() falsely implied one snapshot.

## Correction / recurrence gate

Preserve per-channel revisions and consistency; global catalog revision exists only when all observed revisions agree.
