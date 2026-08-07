# STEP063A — Windows Symlink Integrity Test Portability Fix

## Baseline

- predecessor: `STEP063_STRICT_ENCRYPTED_SQLITE_SESSION_HISTORY_V1` version `2.43.0`;
- current version: `2.43.1`;
- current STEP: `STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX`;
- implementation state: deterministic accepted, Windows rerun pending.

## Evidence-driven problem

The first real Windows STEP063 run passed 32 of 33 checks. The only failure was `focused_strict_encryption_tests_pass`. Pytest reported `52 passed, 1 skipped`; the focused files contain one `pytest.skip()` path, in `test_session_database_symlink_is_rejected`, when the host cannot create a symbolic link.

The Session runtime itself already rejects an existing symlink through `_validate_database_path()`. The failure was therefore an environment-dependent test setup, not an encryption or Session runtime failure.

## Change

Replace real symlink creation with deterministic `Path.exists()` and `Path.is_symlink()` simulation scoped to `runtime.history_db`. The test now reaches the exact production rejection branch on every supported operating system and asserts the exact `SessionIntegrityError` message.

## Non-goals

No change to:

- Session encryption or key derivation;
- SQLite persistence;
- Session catalog migration;
- lifecycle key fencing;
- clear/recreate behavior;
- historical Session compositions;
- Node CLI or committed TypeScript release;
- STEP062 orchestration.

## Windows closure

Run:

```cmd
sh_run_step063a_acceptance.cmd
```

The gate must include a corrected STEP063 result of 33/33 with 53 focused tests passed and zero skipped tests. STEP064 remains unselected.
