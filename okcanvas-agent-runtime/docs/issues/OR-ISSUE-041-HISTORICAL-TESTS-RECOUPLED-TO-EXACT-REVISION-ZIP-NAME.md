# OR-ISSUE-041 — Historical tests re-coupled to an exact revision ZIP filename

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_RERUN_PENDING
STEP: STEP081A_WINDOWS_NPM_COMMAND_RESOLUTION_AND_ACCEPTANCE_PORTABILITY
```

## Exact symptom

The first STEP081A full regression failed three tests in the 140–159 file range. A repository-wide search found a fourth identical assertion:

```text
assert "okcanvas-agent-runtime-step081-root-package-and-architecture-restructuring.zip" in package_source
```

## Root cause

OR-ISSUE-026 previously replaced an older STEP080A filename with the then-current STEP081 filename, but the recurrence gate still encoded one exact revision name. Creating the corrective STEP081A distribution therefore broke unrelated historical feature tests again.

## Impact

The Product code and packaging function were correct, but historical tests could not survive a legitimate corrective revision. Replacing STEP081 with STEP081A text would only defer the same failure to the next revision.

## Fix

All affected tests now import `scripts.package_source.DEFAULT_OUTPUT` and validate `DEFAULT_OUTPUT.name`. The packaging filename has one executable source of truth and historical feature tests no longer own revision-specific names.

## Recurrence-prevention gate

A repository search must find no hardcoded prior STEP081 distribution filename in executable tests or scripts. Full Python and Fresh-ZIP regression must pass after every package revision.
