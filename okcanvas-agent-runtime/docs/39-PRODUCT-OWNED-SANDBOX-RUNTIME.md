# Product-owned Sandbox Runtime

## Purpose

The Sandbox Runtime is a server-owned governed capability. STEP073 established immutable policy,
provider identity, Runtime binding and metadata-only service contracts. STEP074 proved the hardened
local-Docker lifecycle. STEP075 adds the first Product-owned read-only Sandbox workspace Agent.

## Current state

```text
foundation: enabled
provider lifecycle: Windows Docker live accepted
Agent Sandbox execution: enabled for one exact Agent only
provider: docker-local-v1 / product-owned-readonly-workspace-agent-v1
active workspace access: none,sandbox-readonly-v1
physical workspace: bounded Docker tmpfs snapshot only
network/ports: none/[]
host/remote/Docker-socket mounts: disabled
container secrets/environment injection: disabled
runtime image pull: disabled
resume/snapshot: disabled
Shell/Apply Patch: disabled/disabled
Skill materialization: disabled
```

## Read-only workspace

The source directory is never mounted into Docker. The Product creates a canonical bounded text
snapshot, normalizes accepted text to UTF-8, records per-file SHA-256 and copies the snapshot to a
root-owned `noexec,nosuid,nodev` tmpfs at `/workspace`. The container runs as 65532:65532 under the
STEP074 security/resource controls.

The model receives one strict Function Tool. The Tool may execute Product-fixed direct Docker
commands from the allowlist `find`, `cat`, `grep`, `tail`; V1 uses `find` and `cat`. Shell parsers,
command strings and model-selected executables are absent. Every selected file read from the
container must hash to the immutable snapshot entry.

## Agent and Tool

```text
sandbox-readonly-coding-agent
  workspace_access: sandbox-readonly-v1
  Tool: sandbox_project_readonly_inspect
  output: CodingAgentResult
```

All predecessor Agents remain `workspace_access=none`. The Sandbox Agent has no MCP, Hosted Tool,
Handoff, Agent-as-Tool, Skill, Session or Guardrail.

## Evidence and cleanup

Persisted `tool.completed` evidence includes snapshot/image-binding hashes, bounded counts,
selected-file hash verification, Docker call count, cleanup state and orphan count. Raw workspace
content, Tool arguments/results, host path and image reference are not persisted. Cleanup is forced
in `finally`; any deletion failure or nonzero orphan count fails the Tool.

## Why SDK defaults remain rejected

The retained SDK defaults include Filesystem, Shell and Compaction, with Apply Patch inside the
Filesystem bundle. The retained SDK Docker client may pull a missing image and has privileged mount
paths. Product code uses neither SDK Sandbox defaults nor its Docker client.

## Deferred sequence

1. Windows live acceptance of this read-only Agent;
2. independent service `agent-cli` with Sandbox event/artifact visibility;
3. patch-only export;
4. bounded Shell execution;
5. Product Skill materialization and explicit lazy loading.

## STEP075A Docker inspect normalization and failure evidence

Docker `HostConfig.Tmpfs` is an unordered option serialization and may normalize mode and size
notation. Product validation therefore compares the required security meaning: `rw,noexec,nosuid,nodev`,
32 MiB, UID/GID 0 and mode 0755. It does not accept a missing security flag, permissive mode,
malformed value, duplicate key-value option or unknown key-value option.

Before an SDK error can collapse a Sandbox Tool failure into a generic Run failure, Product code
emits one bounded `tool.failed` Event with the stable `SandboxDockerError.code`. The Event contains no
Tool arguments, result, source, host path, image reference, secret or exception message. Preserved
acceptance Product databases are stored at `databases/product.sqlite3`.

## STEP075B operation-level failure evidence

A non-zero Product Docker CLI result is represented by a closed operation identity, integer return
code, bounded stderr category, truncation bit and post-failure cleanup/orphan outcome. Raw Docker
arguments, paths, image references, stdout/stderr, source content and secrets are not persisted. The
primary operation failure is retained through cleanup. STEP075B does not claim the underlying
STEP075A command root cause until a Windows rerun produces the new evidence.

## STEP075C deterministic tar materialization

Product workspace materialization does not use host-path `docker cp`. It creates deterministic GNU tar bytes from the validated snapshot and streams them to the fixed root extractor `tar -x -f - -C /workspace`. Model-visible reads remain fixed non-root commands.

## STEP075D Python subprocess stdin contract

Python `subprocess.run(input=...)` creates the stdin pipe internally. Product input-bearing Docker calls therefore pass `input` only and omit `stdin`; no-input calls pass DEVNULL and omit `input`. A real child-process round-trip validates the adapter. Invalid runner configuration is converted to bounded Product evidence without persisting exception text or stdin bytes.

## STEP075E immutable evidence domain

Product-owned staging metadata may be materialized for internal verification, but it is not project evidence. Sandbox read-only inspection supplies an exact allowed path domain equal to immutable `SandboxSnapshotEntry.path` values. Any selected path outside that domain fails with `SANDBOX_SELECTED_FILE_NOT_IN_SNAPSHOT`; `SANDBOX_SELECTED_FILE_HASH_MISMATCH` is reserved for actual in-domain byte divergence.

## STEP075F exact evidence output completeness

STEP075E Windows live execution proved the Docker/tar/tmpfs/hash-domain runtime path but produced a schema-valid answer that omitted the exact requested formula and constant assignment and placed an evidence-backed file under `unverified`.

STEP075F adds a Product-owned pre-Artifact completeness gate for the read-only Sandbox Agent. For explicit exact formula, signature, assignment, constant-value, identifier, operator or literal requests, the Product derives required fragments from the bounded in-memory Tool evidence and validates the structured answer. Evidence-backed paths cannot be marked unverified.

When the first answer is incomplete, the Product permits exactly one separate correction model call. The correction Agent has no Tool, MCP, Handoff, filesystem, Shell, network or write capability and cannot replay the Sandbox Tool. The corrected answer is validated again; persistent incompleteness fails closed with `ANSWER_COMPLETENESS_FAILED` before Artifact registration.

Completeness Events persist only counts and booleans. Raw request, source evidence, draft and repair prompt are not persisted. Docker lifecycle, immutable snapshot, deterministic tar, root-only materialization, non-root reads, selected-file hash verification, cleanup and orphan reconciliation remain unchanged.

## STEP075G deterministic exact-evidence completion

STEP075F demonstrated that a separate no-tool correction model call is still probabilistic even when all required exact evidence is already available. STEP075G removes that call from the active path. The Product appends one bounded confirmed finding containing only exact fragments derived from the immutable Tool result, includes repository-relative line evidence, removes evidence-backed paths from `unverified`, and re-runs the same completeness validator. Completion adds zero model calls and zero Tool calls. Docker, tar, tmpfs, non-root reads, hash verification, cleanup and orphan reconciliation are unchanged.

## STEP076 immutable service project snapshot

STEP075G Windows live acceptance closed the read-only Agent and deterministic answer-completion path. Code audit then proved the multi-user service boundary still selected source through one process-global host directory rather than submission-owned bytes.

STEP076 adds authenticated bounded ZIP ingress at `/v1/service/project-snapshots`. The Product validates safe repository-relative paths, compression, CRC, symlink/encryption flags and all byte/count limits; computes exact archive and canonical manifest SHA-256 identities; encrypts the ZIP under a dedicated AES-256-GCM subkey; and registers a principal-owned upload slot.

The Sandbox Agent's governed preflight now requires that slot. Snapshot identity enters the request fingerprint, protected payload and SQLite submission ledger. At execution the Product authenticates and revalidates the ZIP, materializes it into a new temporary directory, verifies every file SHA/length, and supplies only that directory to the existing read-only Sandbox Tool. Temporary plaintext is deleted in `finally`.

Only compact hash/count evidence is persisted. Raw ZIP/source, file list, upload filename and host path are excluded from Events and the snapshot evidence Artifact. A successful terminal run deletes the encrypted bound snapshot with its protected payload; failed runs retain both under the existing bounded investigation policy.

The legacy global workspace root is retained only for direct development compatibility. It is not accepted by the governed service submission path.

## STEP077 binary ingress slot lifecycle

STEP076 closed immutable submission binding but left encrypted ingress files and the SQLite ownership projection as separate lifecycle components. STEP077 reconciles authenticated expired snapshot and attachment slot envelopes before upload and governed preflight, then releases the matching ownership rows. Both ingress routes compensate encrypted-file creation if ownership registration fails.

Authenticated principals may explicitly abandon unused slots through `DELETE /v1/service/project-snapshots/{id}` and `DELETE /v1/service/local-attachments/{id}`. Exact principal ownership is required and cross-scope access remains 404. The lifecycle path stores no raw content or secret material and does not change the accepted read-only Sandbox execution boundary.

