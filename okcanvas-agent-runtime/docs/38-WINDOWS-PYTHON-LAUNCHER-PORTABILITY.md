# Windows Python launcher portability constitution

## Status

This constitution is binding for every current and future Windows Python launcher in
`okcanvas-agent-runtime`. It records the real STEP072 → STEP072A → STEP072B failures and the accepted
corrections so the same failure classes are not reintroduced.

STEP072B is Windows-live accepted:

```text
Deterministic acceptance: 24/24 PASS
Live acceptance: 17/17 PASS
Model: gpt-4.1
Model calls: 1
Terminal status: SUCCEEDED
Provider trace diagnostics: none
```

Compact evidence is stored in
`docs/evidence/STEP072B_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.

## Incident 1 — stale timestamp-and-size bytecode collision

Direct ZIP inspection found the same archive timestamp and the same byte size for the STEP071 and
STEP072 copies of:

```text
src/okcanvas_agent_runtime/service_clients/routes.py
archive timestamp: 2026-07-31 03:00:00
size: 32,523 bytes
```

Only an equal-length STEP marker changed. When a newer ZIP was overlaid onto an existing Windows
working directory, an adjacent old `.pyc` remained eligible for Python's timestamp-and-size cache
validation. The STEP072 source was correct, but one imported module returned the prior STEP071 service
policy value.

### Binding prevention

1. Every current Windows Python launcher starts through `scripts/python_bytecode_isolation.py`.
2. The wrapper creates a process-owned temporary `PYTHONPYCACHEPREFIX` outside the project before the
   child interpreter starts.
3. Nested Python children inherit the same prefix.
4. The creating wrapper removes the temporary prefix after the child exits.
5. Source packages exclude `__pycache__`, `.pyc`, and `.pyo` files.
6. A fresh extraction directory remains the preferred operational practice; deleting a local
   `__pycache__` manually is not the product fix.
7. Acceptance must prove both the environment value and the active interpreter value:
   `os.environ["PYTHONPYCACHEPREFIX"]` and `sys.pycache_prefix`.

Canonical launcher composition:

```text
.venv\Scripts\python.exe
  scripts\python_bytecode_isolation.py
    scripts\windows_entrypoint.py <command>
```

A new launcher may bypass `windows_entrypoint.py` only when it requires no local configuration. It
must not bypass `python_bytecode_isolation.py`.

## Incident 2 — Windows CRLF changed a byte-exact fixture

The first STEP072A Windows deterministic run observed 19 bytes while the test compared the file with
an 18-byte LF payload. `Path.write_text()` performed platform newline translation.

### Binding prevention

1. A test that asserts exact byte length, hash, archive identity, parser bytes, or stale-bytecode
   collision behavior must use the byte-exact `Path.write_bytes` API, normally:

```python
path.write_bytes(text.encode("utf-8"))
```

2. `Path.write_text()` is allowed only when platform text semantics are intended and no byte-exact
   assertion depends on the output.
3. Tests must distinguish character content from filesystem bytes. Do not compare a pre-translation
   UTF-8 length with a file written through platform text translation.
4. Cross-platform portability tests must run without assuming LF-only filesystem content.

## Incident 3 — bytecode wrapper bypassed the local environment loader

The first STEP072A live run proved bytecode isolation was present, active, and outside the project,
but reported:

```text
OPENAI_API_KEY_MISSING
OKCANVAS_AGENT_MODEL_MISSING
```

The launcher invoked the live script directly through the bytecode wrapper and bypassed
`scripts/windows_entrypoint.py`, which owns the data-only `.env.local` loading path.

### Binding prevention

1. `.env.local` is configuration data. It must never be `call`ed, sourced, executed, printed, or
   copied into Evidence.
2. `scripts/windows_entrypoint.py` is the sole Windows local-environment parser and allowlisted child
   environment composer.
3. Configuration-bearing launchers use this exact order:

```text
python_bytecode_isolation.py
  -> windows_entrypoint.py
       -> parse .env.local as data
       -> merge allowlisted values into child environment
       -> execute the target with shell=False
```

4. Secrets and model settings are environment values, never command-line arguments.
5. The inherited `PYTHONPYCACHEPREFIX` must survive environment merging.
6. Live acceptance must prove the current interpreter sees the model and pycache prefix, while only
   presence—not the API Key value—is reported.

## New Windows launcher review checklist

Before adding or changing a `.cmd` launcher, verify all of the following:

- uses `.venv\Scripts\python.exe` explicitly;
- uses `scripts\python_bytecode_isolation.py`;
- routes configuration-bearing commands through `scripts\windows_entrypoint.py`;
- invokes children with an argument vector and `shell=False`;
- does not place secrets in arguments or output;
- preserves inherited `PYTHONPYCACHEPREFIX`;
- validates local environment readiness in the actual child interpreter;
- excludes live Evidence, `.env.local`, bytecode caches, virtual environments, and raw attachments
  from packaging;
- has focused Windows composition tests and a real Windows acceptance command;
- records failures before replacing them with corrected evidence.

## Regression and evidence anchors

```text
scripts/python_bytecode_isolation.py
scripts/windows_entrypoint.py
tests/test_step072a_windows_pycache_overlay_isolation_fix.py
tests/test_step072b_windows_crlf_and_local_env_forwarding_fix.py
scripts/run_step072b_acceptance.py
scripts/run_step072b_live_acceptance.py
docs/reference/STEP072A_WINDOWS_PYCACHE_OVERLAY_ISOLATION_FIX_CODE_AUDIT.md
docs/reference/STEP072B_WINDOWS_CRLF_AND_LOCAL_ENV_FORWARDING_FIX_CODE_AUDIT.md
docs/evidence/STEP072A_WINDOWS_ACCEPTANCE_SUMMARY.json
docs/evidence/STEP072B_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json
```

The regression tests are the executable guard. This document is the design and review guard. Both
must remain aligned.
