# STEP075B Windows Docker command operation evidence — code audit

## Audited predecessor evidence

- STEP075A Windows deterministic acceptance: 31/31 PASS.
- STEP075A live acceptance: 13/29 FAILED.
- Persisted Event rows: `tool.started`, `tool.failed`, `agent.failed`, `run.failed`.
- `tool.failed.code`: `DOCKER_COMMAND_FAILED`.
- Failed operation, return code, stderr class and cleanup state: not persisted.

## Code-confirmed diagnostic defect

`ProductOwnedReadonlySandboxInspector._checked()` converted every non-zero Docker CLI result to the
same `SandboxDockerError("DOCKER_COMMAND_FAILED", ...)`. `openai_gateway.py` persisted only the code
and detail type. The inspector's `finally` path could also run removal and orphan commands after the
primary failure, but the original exception had no post-cleanup fields. Therefore the exact command
stage could not be recovered from Product evidence.

## Implemented correction

- `docker_operation_name()` maps only approved Docker CLI shapes to a stable operation identity.
- `docker_stderr_category()` classifies already-bounded output into a closed non-secret category.
- `SandboxDockerError` carries operation, return code, truncation and cleanup/orphan fields.
- The read-only inspector catches the primary Sandbox error, performs cleanup/orphan reconciliation,
  attaches the outcome, then re-raises the same primary error.
- Orphan-check failure does not overwrite an earlier operation failure.
- `tool.failed` persists only bounded fields plus explicit raw-persistence false markers.

## Security review

No Docker argument, Windows path, source path, image reference, stdout, stderr, Tool result,
exception message or secret is included in the Event. The operation vocabulary cannot encode those
values. Existing network-none, no-mount, non-root, read-only-rootfs, cap-drop, tmpfs, no-Shell and
cleanup contracts are unchanged.

## Reference decision

No upstream SDK Sandbox or Docker implementation was imported. This remains Product-owned Docker CLI
execution. The retained OpenAI Agents SDK is involved only in the existing governed Function Tool
run; Product `tool.failed` evidence is emitted before SDK error normalization.

## Remaining uncertainty

STEP075B intentionally does not claim which command failed in STEP075A. The next Windows live run is
required. A second failure must expose a stable operation and bounded classification; only then may a
root-cause fix be selected.

## Deterministic result

```text
STEP075B Acceptance: 34/34 PASS
Focused: 107/107 PASS
Historical: 47/47 PASS
Full Python: 817/817 PASS across 208 files
Node: 14/14 PASS
Reference: 4/4 PASS
npm pack: 23 files PASS
Docker/network/model calls: 0/0/0
```
