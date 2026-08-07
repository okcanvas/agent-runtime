# OR-ISSUE-045 — STEP081A launcher wrappers lacked direct-execution root bootstrap

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_RERUN_PENDING
STEP: STEP081A_WINDOWS_NPM_COMMAND_RESOLUTION_AND_ACCEPTANCE_PORTABILITY
```

## Exact symptom

Direct execution of the new canonical deterministic script failed before argument parsing:

```text
python scripts/run_step081a_acceptance.py
ModuleNotFoundError: No module named 'scripts'
```

The canonical Windows launcher invokes this exact file through `python_bytecode_isolation.py`, so the corrected npm resolver would not have been reached.

## Code-confirmed root cause

Both `run_step081a_acceptance.py` and `run_step081a_live_acceptance.py` imported another `scripts.*` module before placing the project root on `sys.path`. Direct script execution sets `sys.path[0]` to the `scripts/` directory rather than its parent. The older delegated modules already had correct root bootstrapping, but the new wrappers did not.

## Impact

- `sh_run_step081a_acceptance.cmd` would fail immediately on Windows.
- `windows_entrypoint.py` dispatch to `run_step081a_live_acceptance.py` could fail for the same reason.
- The fix for OR-ISSUE-040 would exist but remain unreachable through the canonical STEP081A launchers.

## Fix

Each STEP081A wrapper resolves `ROOT = Path(__file__).resolve().parents[1]`, inserts it into `sys.path`, and only then imports the delegated implementation.

## Recurrence-prevention gates

- `tests/test_step081_direct_script_bootstrap.py` executes both wrappers with `--help` from an unrelated directory and no `PYTHONPATH`.
- STEP081A launcher registry and Windows launcher tests.
- Integrated STEP081A deterministic and Fresh-ZIP Acceptance.
