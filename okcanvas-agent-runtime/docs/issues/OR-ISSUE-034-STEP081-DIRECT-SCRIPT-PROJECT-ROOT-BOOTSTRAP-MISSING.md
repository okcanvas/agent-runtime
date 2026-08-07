# OR-ISSUE-034 — STEP081 direct scripts imported repository modules before project-root bootstrap

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

Direct execution of the baseline-inventory generator failed before argument parsing:

```text
ModuleNotFoundError: No module named 'scripts'
```

The same import ordering existed in `scripts/package_source.py` and could break deterministic packaging when invoked by file path outside a preconfigured repository `PYTHONPATH`.

## Code-confirmed root cause

Both scripts imported `scripts.step081_product_inventory` before inserting the repository root derived from `Path(__file__)` into `sys.path`. Python direct-script execution places the script directory, not its parent repository, at `sys.path[0]`.

## Impact

STEP081 could pass module-based tests while its canonical direct generator and packaging entrypoint failed in a fresh shell. This blocked exact STEP080A-to-STEP081 product inventory generation and final ZIP creation.

## Fix

Each script now resolves `ROOT`, inserts it into `sys.path`, and only then imports the shared inventory module. No environment-specific `PYTHONPATH` is required.

## Recurrence-prevention gate

`tests/test_step081_direct_script_bootstrap.py` executes both scripts by absolute file path from a directory outside the repository. The generator must expose `--help`, and the packager must create a readable canonical-root ZIP without inherited `PYTHONPATH`.
