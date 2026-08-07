# OR-ISSUE-059 — npm pack validation used `--prefix` without the package working directory

## Symptom

A manual STEP082B non-Python validation invoked `npm --prefix clients/cli pack --dry-run --json`. npm attempted to read the repository-root `package.json` and returned ENOENT instead of inspecting `clients/cli`.

## Code-confirmed root cause

For this npm version, `pack` selected its package from the process working directory; `--prefix` did not provide the intended package working directory for this command. The existing portable helper already accepts an explicit `cwd`, but the manual command bypassed it.

## Impact

Node build/tests, Reference validation and installation validation succeeded. Only the manual npm-pack invocation was invalid; it was not evidence of a Client package defect.

## Correction

STEP082B adds `validate_step082b_non_python.py`, which invokes `run_npm_pack(CLI_ROOT)` and therefore executes `npm pack --dry-run --json` with `clients/cli` as the actual working directory.

## Recurrence gate

- `scripts/validate_step082b_non_python.py`;
- exact one-package/23-entry npm pack assertions;
- STEP082B integrated and fresh validation.
