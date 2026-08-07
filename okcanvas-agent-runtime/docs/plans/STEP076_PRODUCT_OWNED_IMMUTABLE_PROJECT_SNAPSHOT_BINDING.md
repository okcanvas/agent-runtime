# STEP076 — Product-owned immutable project snapshot binding

## Identity

```text
STEP076_PRODUCT_OWNED_IMMUTABLE_PROJECT_SNAPSHOT_BINDING
version: 2.56.0
state: IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING
```

## Predecessor closure

STEP075G Windows live acceptance is accepted 38/38. It used exactly two model calls and one Tool call, returned the exact formula and constant, emitted no repair Events, verified the selected file, and completed cleanup with zero orphans. `deterministic_completion_applied=false` is valid because the first structured answer was complete. The previous handoff's 37-check statement was stale: `api_key_not_in_summary` is appended after the initial 37 checks, producing 38.

## Problem selected from code audit

The STEP075G service execution path did not accept a project input per submission. `OpenAIGenericAgentGateway` held a single `readonly_workspace_root`, while service preflight, protected payload, submission ledger and ownership contracts had no project snapshot identity. This allowed time-of-check/time-of-use drift and prevented safe multi-user project separation.

## Product contract

### Ingress

```text
POST /v1/service/project-snapshots
Authorization: Bearer <service token>
X-OKCanvas-Project-Snapshot-Filename: project.zip
body: bounded ZIP bytes
```

The endpoint is Agent-user-only and creates one principal-owned `project-snapshot-slot`.

### ZIP policy

```text
max archive bytes: 16 MiB
max expanded files: 3,000
max expanded bytes: 32 MiB
max single file: 512 KiB
max path: 512 characters
slot TTL: 3,600 seconds
compression: stored or deflated
symbolic links: forbidden
encrypted entries: forbidden
```

Absolute paths, `..`, backslashes, control characters, duplicate/case-colliding paths, reserved internal metadata, unsupported compression, invalid CRC and empty archives fail closed.

### Identity

Two identities are retained:

- `archive_sha256`: exact uploaded ZIP bytes;
- `snapshot_sha256`: SHA-256 of a canonical sorted manifest containing each repository-relative path, file SHA-256 and byte length.

The submission fingerprint and SQLite ledger bind:

```text
project_snapshot_sha256
project_snapshot_archive_sha256
project_snapshot_file_count
project_snapshot_total_bytes
```

### Encryption and lifecycle

Slots and bound snapshots use AES-256-GCM with a project-snapshot-specific derived subkey and authenticated metadata. Preflight atomically binds the slot to the submission and deletes the upload slot. Execution authenticates and revalidates the bound archive before scheduling.

A new temporary directory is created per execution. Every materialized file must match the bound path, byte length and SHA-256. The directory is removed in `finally`.

Successful terminal execution deletes the encrypted bound snapshot together with the protected payload. Failed execution retains both under the existing bounded investigation window.

### Evidence minimization

The Product may persist only a compact `agent.project-snapshot-evidence` Artifact:

```text
snapshot_sha256
archive_sha256
archive_byte_length
file_count
total_bytes
raw_archive_persisted: false
host_path_persisted: false
```

The raw ZIP, raw source, file list, upload filename, host path and encryption material are not placed in the Artifact or Events.

## Compatibility boundary

The existing global `OKCANVAS_READONLY_WORKSPACE_ROOT` remains for direct/development execution tests. It is not the governed service path: service preflight requires `project_snapshot_id` for `sandbox-readonly-coding-agent`.

## Acceptance

Deterministic acceptance must prove:

- STEP075G Windows closure is recorded exactly;
- policy and runtime flags are exact;
- upload/ownership/preflight/fingerprint/payload/ledger/execution/lifecycle are bound;
- ZIP attacks and bounds fail closed;
- encrypted tamper detection and temporary cleanup pass;
- service vertical flow passes without a global workspace root;
- full Python, Node, reference and package checks pass;
- deterministic model, Docker and external-network calls are zero.

The packaged deterministic acceptance contains exactly 37 checks. Its canonical fixture archive SHA-256 is `4bb56ab0be2d823b65221c5b6e997b3ebea6d3b9e0026a26a6266526de9e65ce`; the canonical manifest SHA-256 is `9ee28d0d5cf9c196344e5cc578fc1294e81e817309acdf228a26bc1e27bba54e`.

Windows live acceptance must additionally prove:

- upload via `/v1/service/project-snapshots`;
- mutate the original host source after upload;
- run still returns `SAFETY_STOCK = 12`, never the host mutation `999`;
- exactly two model calls and one Sandbox Tool call;
- compact snapshot evidence hashes match the upload;
- bound snapshot and protected payload are deleted on success;
- Docker security, selected hashes, cleanup and zero-orphan checks remain intact.
