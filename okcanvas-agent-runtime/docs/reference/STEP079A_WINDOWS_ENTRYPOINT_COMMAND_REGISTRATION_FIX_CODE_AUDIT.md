# STEP079A code audit

## Source inspected

- `sh_run_step079_live_acceptance.cmd`
- `scripts/windows_entrypoint.py`
- `scripts/run_step079_live_acceptance.py`
- `scripts/run_step079_acceptance.py`
- `tests/test_windows_entrypoint.py`
- `tests/test_step079_product_owned_atomic_task_run_ownership_transfer.py`

## Confirmed failure path

The launcher command was exact. The dispatcher branch was exact. `_parser().parse_args()` rejected the command because the choices tuple ended with the STEP078 command. Direct reproduction on the extracted ZIP returned exit code 2 and the same invalid-choice error shown by Windows.

## Corrective implementation

- Added the command to the parser choices.
- Changed the existing dispatch branch to `run_step079a_live_acceptance.py`.
- Set `OKCANVAS_STEP079_LIVE_ACCEPTANCE=1` for compatibility and `OKCANVAS_STEP079A_LIVE_ACCEPTANCE=1` for the corrective identity.
- Added `tests/test_step079a_windows_entrypoint_command_registration.py` to execute `windows_entrypoint.run()` under a mocked subprocess and assert the exact Python executable, script path, cwd, environment, and return code.
- Retained the original STEP079 launcher name and added canonical STEP079A launchers.

## Preserved product behavior

No file under Task/Run ownership transaction implementation, project snapshot materialization, Sandbox lifecycle, model gateway, Tool execution, or result completion was changed for the fix. The STEP079 feature regression remains part of STEP079A focused acceptance.

## Previous gate weakness

The STEP079 acceptance used independent source-substring checks. It did not prove parser reachability. STEP079A replaces this blind spot with executable parser and dispatch tests and checks their presence in deterministic acceptance.
