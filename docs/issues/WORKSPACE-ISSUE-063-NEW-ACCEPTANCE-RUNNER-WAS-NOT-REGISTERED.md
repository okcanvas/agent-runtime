# WORKSPACE-ISSUE-063 — New acceptance runner was not registered

## Status

FIXED_IN_STEP096A

## STEP

STEP096A / Workspace R11

## Observation

The STEP096A deterministic runner and Windows launcher existed, but the canonical Runtime acceptance launcher registry still classified STEP094R2 as CURRENT and did not register the new pair. The fail-closed registry validator detected the drift during packaging.

## Correction / recurrence gate

STEP096A is now the exact CURRENT deterministic script/launcher pair; STEP094R2 is historical. Every new acceptance entrypoint must update and pass `validate_acceptance_launcher_registry.py` before packaging.
