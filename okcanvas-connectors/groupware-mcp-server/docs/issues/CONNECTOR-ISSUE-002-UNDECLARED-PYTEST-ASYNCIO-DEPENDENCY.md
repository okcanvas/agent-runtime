# CONNECTOR-ISSUE-002 — Undeclared pytest async plugin dependency

## Failure evidence

A fresh Windows virtual environment installed with the documented command:

```cmd
.venv\Scripts\python.exe -m pip install -e . pytest
```

Then `scripts\run_acceptance.py` failed three async tests. Pytest reported that async functions are
not natively supported and emitted `PytestUnknownMarkWarning` for `pytest.mark.asyncio`. Six sync
tests passed.

## Root cause

The tests depended on `pytest-asyncio`, but neither `pyproject.toml` nor the setup instructions
declared or installed that plugin. Earlier local acceptance was contaminated by an incidental plugin
installation in the build environment.

## Closure

STEP001R1 converts the three tests into normal pytest functions and runs their actual async HTTP
scenarios with Python `asyncio.run()`. This keeps the production behavior under test without a
third-party pytest event-loop plugin. `pyproject.toml` now exposes a canonical `[test]` extra for
pytest itself, while the previously documented `pip install -e . pytest` command remains sufficient.

## Recurrence gate

- `tests/test_contracts.py` rejects `pytest.mark.asyncio` and `pytest_asyncio`;
- `scripts/run_acceptance.py` exposes `async_test_runner_dependency_closed`;
- acceptance must pass in a fresh environment containing project dependencies plus pytest only.
