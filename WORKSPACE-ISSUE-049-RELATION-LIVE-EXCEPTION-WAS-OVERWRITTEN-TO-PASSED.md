# WORKSPACE-ISSUE-049 — relation Live exception was overwritten to PASSED after cleanup

## Status
FIX_IMPLEMENTED_LIVE_RERUN_REQUIRED

## Actual symptom
The same R9A log contained a real ASGI exception but ended with `state=PASSED`, `passed_checks=6`, `total_checks=6`.

## Root cause
The exception payload used only successful preflight checks. Finalization appended successful cleanup and recomputed state with `all(checks.values())`, losing the earlier FAILED state.

## Prevention
Live harnesses must carry an explicit execution-success check and finalization must never promote a payload whose prior state was FAILED.
