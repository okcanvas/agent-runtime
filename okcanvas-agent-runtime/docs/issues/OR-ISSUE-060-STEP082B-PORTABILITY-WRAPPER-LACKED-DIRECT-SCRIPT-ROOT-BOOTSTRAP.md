# OR-ISSUE-060 — STEP082B portability wrapper lacked direct-script root bootstrap

## Symptom

Direct execution of `python scripts/validate_step082b_windows_subprocess_portability.py` failed with `ModuleNotFoundError: No module named 'scripts'`.

## Code-confirmed root cause

Python placed the `scripts` directory, not the repository root, at `sys.path[0]`. The new wrapper imported `scripts.validate_windows_subprocess_portability` before inserting the repository root.

## Impact

No portability checks ran and no evidence file was produced. Importing the wrapper through pytest could have hidden the direct-script defect.

## Correction

The wrapper now resolves the repository root from `__file__` and inserts it at the front of `sys.path` before importing repository modules.

## Recurrence gate

- direct execution of `scripts/validate_step082b_windows_subprocess_portability.py`;
- STEP082B integrated acceptance and Windows launcher.
