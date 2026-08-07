# OR-ISSUE-002 — STEP075A Windows Docker command operation evidence

## Status

`DIAGNOSTIC_FIX_IMPLEMENTED_WINDOWS_RERUN_PENDING`

## Exact symptom

STEP075A deterministic acceptance passed 31/31 on Windows. The real live run completed one `gpt-4.1` model turn, emitted `tool.started`, and then emitted `tool.failed` with code `DOCKER_COMMAND_FAILED`. It subsequently emitted `agent.failed` and `run.failed`. No `tool.completed`, final Artifact, positive token total, or successful Sandbox lifecycle evidence was produced. The acceptance workspace was preserved.

The preserved SQLite Event payload confirmed only:

```text
tool.failed.code = DOCKER_COMMAND_FAILED
tool.failed.detail_type = SandboxDockerError
```

It did not contain the failed Docker operation, return code, bounded stderr category, output truncation state, cleanup result, or orphan count.

## Bounded uncertainty

The available evidence does not identify whether `image inspect`, `container create`, `container inspect`, `container start`, `container cp`, `container exec find`, `container exec cat`, `container rm`, or `container ls` failed. This issue therefore does not claim a Docker command root cause.

The STEP075A tmpfs semantic normalization remains a valid portability fix, but the STEP075A rerun proves that it was not the complete cause of the live failure.

## Impact

A non-zero Docker CLI result collapses to one generic code. Operators cannot distinguish image readiness, container creation, startup, workspace copy, direct read command, or cleanup failures without reproducing the run outside the governed Runtime. That violates the project's evidence-first debugging rule.

## Fix

1. Map every allowed Docker command to one stable bounded operation identity.
2. Persist the exact integer return code.
3. Classify bounded stdout/stderr into a closed category without persisting raw output.
4. Persist whether bounded output was truncated.
5. Preserve the primary command failure even if cleanup or orphan reconciliation also fails.
6. Attach cleanup attempted/completed state and orphan count after the `finally` path.
7. Keep raw Docker arguments, paths, image references, source content, stdout/stderr, exception messages, and secrets absent.
8. Route the fields through the existing Product `tool.failed` Event and STEP075B live compact summary.

## Stable operation vocabulary

```text
docker.version
image.inspect
container.create
container.inspect
container.start
container.wait
container.logs
container.copy_snapshot
container.exec.find
container.exec.cat
container.exec.grep
container.exec.tail
container.exec.unknown
container.remove
container.list_orphans
docker.unknown
sandbox.cleanup
```

## Stable stderr categories

```text
DAEMON_UNAVAILABLE
COMMAND_UNAVAILABLE
PERMISSION_DENIED
OPERATION_NOT_PERMITTED
READ_ONLY_FILESYSTEM
EXECUTABLE_NOT_FOUND
NO_SUCH_FILE_OR_DIRECTORY
CONTAINER_NOT_RUNNING
CONTAINER_NOT_FOUND
IMAGE_NOT_FOUND
INVALID_ARGUMENT
RESOURCE_EXHAUSTED
TIMEOUT
UNKNOWN
```

## Evidence

- `docs/evidence/STEP075A_WINDOWS_LIVE_ACCEPTANCE_FAILURE_SUMMARY.json`
- Preserved database relative path `databases/product.sqlite3`
- User-reported Event rows 7–10 for Run `run_961686626d024afe84a6ba5553145b9b`
- `src/okcanvas_agent_runtime/sandbox_runtime/errors.py`
- `src/okcanvas_agent_runtime/sandbox_runtime/docker_cli.py`
- `src/okcanvas_agent_runtime/sandbox_runtime/read_only_workspace.py`
- `src/okcanvas_agent_runtime/execution/openai_gateway.py`

## Automated recurrence prevention

- `tests/test_step075b_windows_docker_command_operation_evidence.py`
- failed image-inspect case with no cleanup needed
- failed workspace-copy case with completed cleanup and orphan zero
- operation vocabulary and bounded stderr category tests
- gateway raw-value non-persistence assertions
- STEP075B deterministic acceptance
- STEP075B Windows live rerun
