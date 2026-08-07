# OR-ISSUE-048 — STEP081B deterministic Acceptance discarded Architecture and Compliance diagnostics

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_VALIDATION_PENDING_WINDOWS_RERUN`

## Observed failure

Real Windows `sh_run_step081b_acceptance` completed all local non-model work but ended `15/18 FAILED`. Architecture reported only `36/38`; the two false Architecture check names and `details` payload were not included. Compliance was false, but unregistered/stale changed-file paths were also omitted.

No OpenAI API request or billing-dependent operation was involved.

## Root cause

`run_step081_acceptance.py` called Architecture and Compliance validators in process and retained only summary fields. Focused regression repeated the failure but could not restore the discarded sub-validator evidence.

## Fix

Both validators execute in isolated Python subprocesses. Acceptance preserves the complete JSON payload and process diagnostic, including return code, parse status, bounded stdout/stderr, false checks, route inventory, project-root failures and Compliance drift.

## Recurrence gates

- `tests/test_step081c_windows_deterministic_architecture_diagnostics_and_topology_normalization.py`
- STEP081C deterministic Acceptance
- Fresh-ZIP deterministic Acceptance
