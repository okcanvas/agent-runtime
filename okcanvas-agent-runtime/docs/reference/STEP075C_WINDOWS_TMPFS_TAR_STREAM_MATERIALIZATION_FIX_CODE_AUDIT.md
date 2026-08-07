# STEP075C code audit

## Audited baseline

STEP075B 2.55.2 and the user-reported Windows live evidence were inspected before modification.

## Confirmed evidence

The persisted failure operation was `container.copy_snapshot`, return code 1. Cleanup completed and orphan count was zero. Product code created `/workspace` as tmpfs and used a host-path `docker container cp` call to populate it.

Docker documents tmpfs and user-created mounts as `docker cp` corner cases and recommends tar streaming through `docker exec`:

- https://docs.docker.com/reference/cli/docker/container/cp/#corner-cases

This aligns the recorded operation with the Product implementation; no other Docker command is claimed as the cause.

## Implementation audit

### Archive

`build_readonly_snapshot_archive()` creates deterministic GNU tar bytes from the already-validated staging tree. It uses sorted safe relative paths, UID/GID 0, empty owner names, mtime 0, directories 0755 and files 0444. It rejects unsafe sources and bounds archive expansion overhead.

### Transport

`SubprocessDockerCommandRunner.run_with_input()` passes bounded bytes directly to `subprocess.run(input=...)` with `shell=False`, a sanitized environment and bounded output capture.

### Materializer

The only root execution is the exact Product-owned argument array:

```text
container exec --interactive --user 0:0 <id> tar -x -f - -C /workspace
```

The command is classified as `container.extract_snapshot`. It is not model-selected and is not part of the read-only Tool command allowlist.

### Post-materialization

Inventory and selected content are still read with fixed non-root `find` and `cat`; selected bytes must match the immutable snapshot hashes. Cleanup/orphan evidence and primary-failure preservation remain unchanged.

## Explicitly absent

- host-path `docker cp` in Product workspace code;
- Shell/parser/eval;
- host or remote mounts;
- network and ports;
- Docker socket;
- container secrets/environment;
- model-selected executable or host path;
- Apply Patch, Skill materialization, resume or snapshot restore.

## Result

The code change addresses the code- and upstream-confirmed STEP075B materialization incompatibility without widening Agent permissions. Windows live rerun remains required.

## Deterministic result

- STEP075C acceptance: 30/30 PASS
- Focused tests: 112/112 PASS
- Historical regression: 47/47 PASS
- Full Python regression: 822/822 PASS across 209 files
- Node: 14/14 PASS
- Reference: 4/4 PASS, direct imports 0
- npm pack dry-run: 23 files PASS
- Docker/network/model calls: 0/0/0

Windows Docker + model rerun remains the only pending acceptance boundary.
