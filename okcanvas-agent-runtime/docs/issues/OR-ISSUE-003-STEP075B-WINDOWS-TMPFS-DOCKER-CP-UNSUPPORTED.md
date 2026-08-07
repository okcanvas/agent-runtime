# OR-ISSUE-003 — STEP075B Windows tmpfs `docker cp` unsupported materialization

## Status

`FIX_IMPLEMENTED_DISTINCT_SUBPROCESS_FAILURE_REMAINS`

## Exact symptom

STEP075B deterministic acceptance passed 34/34. The Windows live run completed one `gpt-4.1` turn and entered `sandbox_project_readonly_inspect`, then failed before Tool completion. Bounded Product evidence recorded:

```text
code = DOCKER_COMMAND_FAILED
operation = container.copy_snapshot
return_code = 1
stderr_category = UNKNOWN
cleanup_attempted = true
cleanup_completed = true
orphan_count = 0
```

No final Artifact was produced. The acceptance workspace was preserved.

## Code-confirmed cause

`ProductOwnedReadonlySandboxInspector.inspect()` created `/workspace` as a user-created tmpfs and then invoked:

```text
docker container cp <Windows staging path>/. <container>:/workspace
```

Docker's official `docker container cp` documentation identifies tmpfs and user-created mounts as corner cases that cannot be copied with `docker cp`, and recommends tar streaming through `docker exec` instead:

- https://docs.docker.com/reference/cli/docker/container/cp/#corner-cases

The recorded failure operation is exactly the unsupported Product operation. The failure is therefore not attributed to tmpfs option ordering, image readiness, container startup, `find`, or `cat`.

## Impact

The first read-only Sandbox Agent could never materialize its canonical snapshot on the accepted Windows Docker Desktop environment, although container lifecycle and cleanup were correct.

## Fix

1. Remove host-path `docker container cp` from the Product workspace path.
2. Build one deterministic GNU tar archive in Python from the already-validated canonical snapshot.
3. Archive entries contain only safe relative files/directories, UID/GID 0, empty owner names, mtime 0, directory mode 0755 and file mode 0444; links and device entries are absent.
4. Stream the bounded archive through stdin to one exact command:

```text
docker container exec --interactive --user 0:0 <container> tar -x -f - -C /workspace
```

5. The root materializer exists only to populate the root-owned tmpfs. Model-visible `find`, `cat`, `grep`, and `tail` remain under the container's configured non-root user `65532:65532`.
6. Shell parsing, host mounts, image pull, network, ports, secrets and model-selected executables remain forbidden.
7. Preserve cleanup/orphan evidence and stable operation identity `container.extract_snapshot`.

## Automated recurrence prevention

- `tests/test_step075c_windows_tmpfs_tar_stream_materialization_fix.py`
- deterministic archive identity and metadata checks
- exact root materializer argument-array check
- no Product `container cp` source path
- bounded stdin runner check
- STEP075C deterministic acceptance
- STEP075C Windows live acceptance

## STEP075C rerun outcome

The tar-stream design removed the unsupported `docker cp` operation, but the first STEP075C live rerun failed before Docker startup because the Python runner passed mutually exclusive `stdin` and `input` arguments. That distinct defect is owned by OR-ISSUE-004; it does not invalidate this issue's confirmed `docker cp` root cause or fix.
