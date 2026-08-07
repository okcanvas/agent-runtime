# OR-ISSUE-042 — Launcher registry current metadata and historical count assertions were stale

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_RERUN_PENDING
STEP: STEP081A_WINDOWS_NPM_COMMAND_RESOLUTION_AND_ACCEPTANCE_PORTABILITY
```

## Exact symptom

The STEP081A full regression reached files 200–219 and failed two launcher-registry assertions:

```text
script_count expected 127, actual 129
registry.current_step remained STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Root cause

Adding the two STEP081A Python scripts and two Windows launchers updated the record list and CURRENT classifications, but the registry top-level `current_step` metadata was not updated. A historical STEP080A regression also owned exact cumulative script/launcher/record counts instead of validating the registry's computed result for the current revision.

## Impact

The registry validator could report its record set as complete while the human-readable current-step metadata remained stale. Historical tests also failed on every legitimate launcher addition.

## Fix

- Set `launcher-registry.json.current_step` to the exact STEP081A identity.
- Update the current cumulative inventory to 129 Python scripts, 124 Windows launchers, and 253 records.
- Retain the exact four CURRENT STEP081A records and all prior records as HISTORICAL.

## Recurrence-prevention gate

Both STEP080A historical registry regression and STEP081/STEP081A current registry regression run in the full suite. The registry validator recomputes actual script and launcher paths and requires exact set equality.
