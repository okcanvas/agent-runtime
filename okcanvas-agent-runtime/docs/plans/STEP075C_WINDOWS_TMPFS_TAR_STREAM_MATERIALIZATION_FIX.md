# STEP075C — Windows tmpfs tar-stream materialization fix

## Identity

```text
STEP075C_WINDOWS_TMPFS_TAR_STREAM_MATERIALIZATION_FIX
version: 2.55.3
```

## Trigger

STEP075B deterministic acceptance passed 34/34. Windows live acceptance failed 13/29 after one model call. Bounded Tool evidence identified the exact failure:

```text
operation: container.copy_snapshot
return_code: 1
stderr_category: UNKNOWN
cleanup_completed: true
orphan_count: 0
```

The Product destination `/workspace` is a user-created tmpfs. Docker's official `docker container cp` documentation states that tmpfs and user-created mounts are unsupported `docker cp` corner cases and recommends tar streaming through `docker exec`.

## Scope

1. Retain the canonical bounded UTF-8 snapshot and root-owned noexec/nosuid/nodev tmpfs.
2. Remove host-path `docker container cp` from the Product workspace materialization path.
3. Build one deterministic GNU tar archive in Python.
4. Stream the archive through stdin to the exact argument-array command:

```text
docker container exec --interactive --user 0:0 <container> tar -x -f - -C /workspace
```

5. Keep model-visible read commands under the configured non-root container user.
6. Preserve all cleanup, orphan, hash-verification and bounded failure evidence.
7. Add `container.extract_snapshot` to the stable operation vocabulary.

## Security invariants

- archive paths are relative and validated;
- links, devices, host paths, owner names and timestamps are absent;
- directory mode is 0755 and file mode is 0444;
- archive UID/GID are 0;
- root is used only by the fixed materializer command;
- no Shell, network, ports, host mount, Docker socket, secret, image pull, patch or dependency install;
- `find`, `cat`, `grep`, `tail` remain the only model-reachable Product commands;
- selected file hashes must match the canonical snapshot;
- cleanup and orphan-zero remain mandatory.

## Acceptance

- STEP075C deterministic checks pass with Docker/network/model calls 0;
- focused archive/runner/materialization tests pass;
- full regression, Node, Reference and package integrity pass;
- Windows live rerun produces two model calls, one Tool completion, verified hashes, completed cleanup and orphan zero;
- STEP076 remains unselected.
