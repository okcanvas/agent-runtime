# STEP064A Code Audit — Pytest Async Plugin Independence

## Files inspected

- `pyproject.toml`
- `requirements-direct.txt`
- `tests/test_step064_bounded_encrypted_sqlite_session_compaction.py`
- `tests/test_sqlite_session_runtime.py`
- `scripts/run_step064_acceptance.py`
- `src/okcanvas_agent_runtime/sessions/compaction.py`
- `src/okcanvas_agent_runtime/sessions/service.py`
- `src/okcanvas_agent_runtime/execution/service.py`
- `src/okcanvas_agent_runtime/tool_approval/service.py`
- `specs/runtime/sqlite-session-policy.json`

## Confirmed facts

1. The project declares `pytest>=8.3,<10` but does not declare `pytest-asyncio`.
2. The STEP064 focused file was the only project test file using `pytest.mark.asyncio`.
3. It contained seven marked async tests and four synchronous tests.
4. Historical Session tests use `asyncio.run()` and passed on the same Windows run.
5. Disabling pytest plugin autoload reproduced `7 failed, 4 passed, 7 warnings` exactly.
6. Therefore the failure was an undeclared ambient-plugin dependency in tests, not a compaction product failure.

## Chosen correction

The seven tests remain async internally but are exposed to pytest through a product-test-owned synchronous decorator using `functools.wraps` and `asyncio.run()`.

`functools.wraps` is required so pytest can preserve fixture signatures for the two tests that receive `tmp_path` and `monkeypatch`.

## Rejected alternatives

### Add `pytest-asyncio`

Rejected. It would add a dependency solely to support seven tests when the repository already uses standard-library `asyncio.run()` successfully.

### Treat the Windows result as an environment setup error

Rejected. The plugin is not declared by the repository, so a clean environment is correct not to contain it.

### Skip async tests without the plugin

Rejected. A skipped product-boundary test is not acceptance evidence.

## Runtime non-change proof

The following predecessor SHA-256 values are fixed in STEP064A tests and acceptance:

```text
0775e58c3ee126a6d5d4327960e57e75de56b82221f8f59216410387b0f23c2e  sessions/compaction.py
0906f3ef39dec46b19ac611f384312e4545baa0759e124b41aca283164bda7ad  sessions/service.py
379e868d22b7b6c216fe2988d875846ed021f53cd8cb86f5630c399f68519d99  sqlite-session-policy.json
f1c7c0f2d0b96a06f0732ab691e7fb8a258f814cb9ed49f26c1ded764c56dec9  execution/service.py
a289ce3fc90bf82b84308e5f220818519f8768648a3833c96bc2bbf2989991c8  tool_approval/service.py
```

## Exact changed implementation surface

- focused STEP064 test adapter and decorators;
- STEP064A baseline/runtime flags;
- corrected predecessor acceptance baseline identity;
- STEP064A test, acceptance launcher and evidence/documents.

No production compaction behavior changed.
