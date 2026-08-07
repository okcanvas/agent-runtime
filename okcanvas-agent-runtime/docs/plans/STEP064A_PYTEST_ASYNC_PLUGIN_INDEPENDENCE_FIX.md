# STEP064A — Pytest Async Plugin Independence Fix

## Baseline

- Project: `okcanvas-agent-runtime`
- Version: `2.44.1`
- Current STEP: `STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX`
- Predecessor: STEP064 version `2.44.0`
- Scope: test/acceptance portability only

## Triggering Windows evidence

The first real Windows STEP064 run passed 28 of 29 checks. The only failure was:

```text
focused_compaction_tests_pass = false
focused output = 7 failed, 4 passed, 7 warnings in 1.90s
```

All product-policy, compaction-runtime, historical Session, compile, committed Node release, Node test, Reference and packaging checks passed.

## Code-audited root cause

`tests/test_step064_bounded_encrypted_sqlite_session_compaction.py` contained exactly seven `@pytest.mark.asyncio` tests and four ordinary synchronous tests. The project declares `pytest`, but does not declare `pytest-asyncio` in either `pyproject.toml` or `requirements-direct.txt`.

Running the exact focused file with:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
```

reproduced the Windows shape exactly:

```text
7 failed, 4 passed, 7 warnings
```

The seven failures stated that async test functions are unsupported without an async pytest plugin. The seven warnings were unknown `pytest.mark.asyncio` warnings.

## Fix

Do not add a new runtime or test dependency. The focused test file now owns a tiny standard-library adapter:

```python
@wraps(function)
def wrapper(*args, **kwargs):
    return asyncio.run(function(*args, **kwargs))
```

Exactly seven async scenarios use `@_async_test`. Pytest sees ordinary synchronous test callables while the production async paths are still executed by `asyncio.run()`.

## Invariants

- No `pytest-asyncio` dependency is added.
- No product Session, compaction, execution, approval or policy source changes.
- STEP064 candidate selection, bounds, encryption, post-commit lease and rollback contracts remain unchanged.
- The focused file must pass with plugin autoload disabled.
- STEP065 remains unselected until Windows closure.

## Acceptance

Run:

```cmd
sh_run_step064a_acceptance.cmd
```

Required results:

- corrected STEP064: 29/29;
- focused STEP064 compaction tests: 11 passed, no skips/warnings/failures;
- plugin-autoload-disabled focused tests: 11 passed;
- STEP064A: all checks pass;
- Node release integrity and 14 Node tests pass;
- References unchanged and no direct Reference imports.
