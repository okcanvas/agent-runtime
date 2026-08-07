# STEP003A — Windows Disposable Cleanup Fix

## Objective

Preserve the authoritative STEP003 acceptance result when Windows temporarily refuses deletion of
an independent-validator `__pycache__` directory, while still recording and retrying disposable
workspace cleanup separately.

## Code-derived trigger

The first real STEP003 Windows execution completed every functional check:

- baseline validator observed one expected failure;
- Codex write succeeded;
- exactly `src/inventory/pricing.py` changed;
- patch evidence existed;
- independent post-validation passed one test;
- source fixture and Git HEAD were unchanged;
- token budget was accepted.

The harness nevertheless returned `FAILED` because exiting `TemporaryDirectory` raised
`PermissionError` while deleting `fixture-repo/src/inventory/__pycache__`.

## In scope

- replace implicit `TemporaryDirectory` teardown with explicit cleanup;
- retry cleanup for transient Windows locks;
- clear read-only attributes during deletion;
- record cleanup state, attempts, duration, and bounded error detail;
- separate core acceptance state from cleanup state;
- return success when all core acceptance checks pass, even if cleanup ends with a warning;
- require a later exact `PASSED` run before marking STEP003 complete.

## Non-scope

- external project mutation;
- STEP004 approval/RunState work;
- MCP, API, SSE, UI, or Windows worker;
- changes to Codex write policy, patch allowlist, token budget, or independent validation.

## State contract

- `PASSED`: core acceptance passed and cleanup completed.
- `PASSED_WITH_CLEANUP_WARNING`: core acceptance passed but cleanup remained incomplete after retries.
- `FAILED`: one or more core acceptance checks failed or execution raised a core error.

Cleanup warnings do not populate the core `error` field and do not erase successful functional
Evidence. They are retained under the separate `cleanup` field.

## Completion criteria

1. Unit tests prove retry after a transient `PermissionError`.
2. Unit tests prove persistent cleanup warning does not reverse core acceptance.
3. Existing STEP003 controls and regression tests remain green.
4. Source ZIP and Reference integrity pass.
5. Windows live rerun returns `state=PASSED`, `core_acceptance_passed=true`, and
   `cleanup.state=COMPLETED` before STEP003 is declared complete.
