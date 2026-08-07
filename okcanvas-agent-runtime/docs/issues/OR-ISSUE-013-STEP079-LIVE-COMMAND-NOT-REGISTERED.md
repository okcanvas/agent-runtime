# OR-ISSUE-013 — STEP079 live command missing from Windows entrypoint parser registry

## Status

`WINDOWS_LIVE_ACCEPTED`

## Exact symptom

The user extracted the canonical STEP079 ZIP on Windows and ran:

```cmd
sh_run_step079_live_acceptance
```

The launcher invoked:

```text
scripts\windows_entrypoint.py atomic-task-run-ownership-transfer-live-acceptance
```

`argparse` exited with code 2 before any live workflow began:

```text
invalid choice: atomic-task-run-ownership-transfer-live-acceptance
```

The usage list ended at `atomic-service-submission-ownership-transfer-live-acceptance`.
No model, Tool, Docker, submission, Task, or Run operation occurred.

## Code-confirmed root cause

`scripts/windows_entrypoint.py` contained an `elif` dispatch branch for `atomic-task-run-ownership-transfer-live-acceptance` and routed it to `run_step079_live_acceptance.py`, but `_parser()` omitted the same command from its immutable `choices` tuple. Argument validation therefore rejected the command before the dispatch branch was reachable.

The STEP079 deterministic acceptance checked that the launcher contained the command and that the entrypoint source contained the live script name, but it did not prove that the command was accepted by the parser and routed by an executable unit test.

## Impact

The packaged Task/Run atomic ownership implementation and deterministic tests were present, but the canonical Windows live launcher was unusable. STEP079 could not be declared Windows-live accepted.

## Fix

STEP079A:

- registers `atomic-task-run-ownership-transfer-live-acceptance` in the parser `choices`;
- keeps the dispatch branch aligned with the parser registry;
- routes both the original STEP079 launcher and the STEP079A launcher to `run_step079a_live_acceptance.py`;
- preserves the original command name for backward compatibility;
- adds an executable parser-and-dispatch regression test;
- adds deterministic acceptance checks for parser registration, dispatch target, environment forwarding, old-launcher compatibility, and exact failure evidence.

## Evidence and recurrence gate

- `docs/evidence/STEP079_WINDOWS_LIVE_ENTRYPOINT_FAILURE_SUMMARY.json`
- `tests/test_step079a_windows_entrypoint_command_registration.py`
- `scripts/run_step079a_acceptance.py`
- `sh_run_step079a_acceptance.cmd`
- `sh_run_step079a_live_acceptance.cmd`

The corrected STEP079A ZIP passed canonical Windows live acceptance 57/57 on 2026-08-02.
