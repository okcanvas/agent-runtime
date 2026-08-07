# OR-ISSUE-049 — STEP081B Acceptance output could invalidate later Compliance runs

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_VALIDATION_PENDING_WINDOWS_RERUN`

## Problem

The default deterministic Acceptance output was the packaged `docs/evidence/STEP081B_ACCEPTANCE.json`. Running Acceptance in place rewrote a protected Product file. A repeated run could therefore fail exact changed-file Compliance even when executable code had not changed.

## Fix

The Windows/user-facing STEP081C launcher writes to `docs/evidence/step081c-local/STEP081C_ACCEPTANCE.json`. That directory is excluded by the shared Product inventory and `.gitignore`. Packaging validation may still create the canonical immutable evidence file explicitly with `--output docs/evidence/STEP081C_ACCEPTANCE.json`.

## Recurrence gates

- shared Product inventory exclusion test
- launcher default-output test
- repeated deterministic Acceptance test
