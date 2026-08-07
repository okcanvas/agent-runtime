# OR-ISSUE-001 — STEP075 Windows Docker tmpfs normalization and failure evidence

## Status

`FIX_DETERMINISTIC_ACCEPTED_DISTINCT_LIVE_FAILURE_CONFIRMED`

## Exact symptom

STEP075 deterministic acceptance passed 28/28 on Windows. The real live run completed one `gpt-4.1` model turn, emitted `tool.started` for `sandbox_project_readonly_inspect`, then emitted `agent.failed` and `run.failed`. No `tool.completed`, final Artifact, token total, or Sandbox lifecycle evidence was produced. The acceptance workspace was preserved.

The first manual SQLite command failed with `sqlite3.OperationalError: unable to open database file` because it used `database/product.sqlite3`. The workspace inventory proved the correct relative path is `databases/product.sqlite3`.

## Code-confirmed root cause defect

`ProductOwnedReadonlySandboxInspector._validate_created_container()` compared Docker's `HostConfig.Tmpfs["/workspace"]` to one exact string. Docker may preserve the same security contract while reordering comma-separated options, representing `mode=0755` as `mode=755`, or representing 33,554,432 bytes as `32m`. Exact string equality is not a portable security validation.

The preserved database's original `SandboxDockerError.code` was not retrieved before this fix, so this document does not claim that the exact-string defect was conclusively the only runtime failure. STEP075A adds exact bounded failure evidence so the next failure, if any, is diagnosable without inference.

## Rerun finding

STEP075A Windows rerun confirmed `DOCKER_COMMAND_FAILED` after the tmpfs semantic fix. The operation was not persisted, so the rerun proves a distinct or additional failure remains and does not invalidate the portability fix. OR-ISSUE-002 owns the missing operation evidence.

## Impact

A secure, non-root, network-none, read-only container could be rejected before start and materialization. The Product Run then failed after `tool.started`, while the live summary exposed only generic Agent/Run failure state.

## Fix

1. Parse tmpfs options semantically and independently of order.
2. Accept exact equivalent forms for size bytes/units and mode `0755`/`755`/`0o755`.
3. Require `rw,noexec,nosuid,nodev`, size 32 MiB, UID/GID 0, and mode 0755.
4. Reject `ro`, `exec`, `suid`, `dev`, missing required flags, relaxed mode, duplicate/unknown key-value options, and malformed values.
5. Emit a bounded `tool.failed` Product Event containing only Tool identity, stable `SandboxDockerError.code`, detail type, and persistence booleans. Raw arguments, result, source, image, host path, and exception text remain absent.
6. Record the correct acceptance database relative path as `databases/product.sqlite3` in failure evidence and operator documentation.

## Evidence

- `docs/evidence/STEP075_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json`
- User-reported STEP075 deterministic 28/28 and live 13/28 output
- Preserved workspace inventory containing `databases/product.sqlite3`
- Source audit of `src/okcanvas_agent_runtime/sandbox_runtime/read_only_workspace.py`

## Automated recurrence prevention

- `test_tmpfs_size_and_mode_normalization_is_exact`
- `test_tmpfs_security_is_order_independent_but_fail_closed`
- `test_inspector_accepts_semantically_equal_windows_tmpfs_normalization`
- `test_inspector_rejects_tmpfs_missing_noexec_and_cleans_up`
- `test_gateway_persists_bounded_sandbox_tool_failure_event`
- STEP075A deterministic acceptance
- STEP075A Windows live acceptance

## Correct preserved-workspace diagnostic

```cmd
.venv\Scripts\python.exe -c "import sqlite3,pathlib; p=pathlib.Path(r'<PRESERVED_WORKSPACE>\databases\product.sqlite3'); c=sqlite3.connect(p); rows=c.execute(\"select sequence,event_type,payload_json from run_event where run_id=? order by sequence\",('<RUN_ID>',)).fetchall(); [print(n,t,j) for n,t,j in rows if t in ('tool.started','tool.failed','tool.completed','agent.failed','run.failed')]"
```
