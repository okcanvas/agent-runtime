# OR-ISSUE-039 — Integrated Acceptance used a stale test path and wrong compliance result schema

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

After canonical imports were fixed, integrated Acceptance completed but reported `12/14 FAILED`:

```text
ERROR: file or directory not found: tests/test_operations_api.py
windows_live_remains_external: false
```

## Code-confirmed root cause

The focused test list retained a removed historical filename; the actual test is `tests/test_operations_console_api.py`. Separately, Acceptance read `pending_external_gate_ids` from the compliance validator's top level, while the validator exposes the normalized pending count under `summary` and the exact Gate check under `checks.windows_only_pending`.

## Impact

A valid focused regression was never executed, and the correctly pending Windows Gate was falsely reported as closed/non-pending.

## Fix

Acceptance now calls the real Operations Console test and requires both `summary.pending_external_gate_count == 1` and `checks.windows_only_pending == true`.

## Recurrence-prevention gate

The STEP081 architecture test inspects the integrated Acceptance source for the canonical test path and structured compliance fields. Integrated and Fresh-ZIP Acceptance must pass all checks.
