# OR-ISSUE-072 — Current launcher regression retained exact STEP083 paths

## Symptom

STEP084 integrated acceptance reached the focused regression but failed because `test_step081_launcher_registry_is_complete_and_current` required the two CURRENT records to remain STEP083 launchers.

## Code-confirmed root cause

The launcher registry validator was successor-safe and correctly reported the STEP084 pair, but a current-state regression independently hardcoded the prior STEP083 script and Windows launcher paths.

## Impact

The canonical STEP084 launchers existed and the registry passed 7/7, yet integrated acceptance remained FAILED.

## Correction

The current-state regression now expects the exact STEP084 Python and Windows launcher pair. Historical STEP083 launchers remain registered as HISTORICAL.

## Recurrence gate

- acceptance launcher registry validation;
- current launcher pair regression;
- STEP084 integrated and Windows acceptance.
