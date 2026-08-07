# OR-ISSUE-008 — Global Sandbox workspace was not submission-bound

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Exact code-confirmed symptom

In the STEP075G packaged baseline, the read-only Sandbox Agent obtained its project from one process-global `OKCANVAS_READONLY_WORKSPACE_ROOT` value:

- `control_api/app.py` accepted and passed `readonly_workspace_root` to the gateway;
- `execution/openai_gateway.py` retained that root on the gateway instance and supplied the same path to every Sandbox Tool execution;
- `GovernedRunPreflightRequest`, `RunSubmissionDecision`, `ProtectedPayloadContent`, the service ownership ledger and service capability contract contained no project snapshot identity.

Therefore the governed submission fingerprint did not identify the project bytes that would be inspected. A file could change after preflight but before execution, and independent service principals could not bind distinct immutable project inputs to concurrent submissions. This was a product contract gap even though STEP075G's single-user Windows fixture was successful.

## Impact

- submission identity covered request/model/Agent but not project bytes;
- queued execution could observe a later host-directory state;
- one server-global path was unsuitable for multi-user service clients;
- retry/audit evidence could not prove which uploaded project snapshot belonged to a submission;
- the host path remained configuration for the active service path.

No claim is made that STEP075G's accepted Windows run was corrupted. The issue is that the code did not make such drift impossible.

## Fix

STEP076 introduces Product-owned immutable ZIP snapshot binding:

1. `POST /v1/service/project-snapshots` accepts one bounded ZIP as raw request bytes under the authenticated service principal.
2. ZIP validation rejects unsafe filenames, absolute/traversal/backslash paths, control characters, duplicate/case-colliding paths, symbolic links, encrypted entries, unsupported compression, CRC errors and all configured size/count overflows.
3. The validated archive receives an archive SHA-256 and a canonical sorted per-file manifest SHA-256.
4. The archive is encrypted at rest with a project-snapshot-specific AES-256-GCM subkey. The raw ZIP is not written into Events or Artifacts.
5. The uploaded slot is principal-owned. Cross-principal and cross-tenant lookup remains 404.
6. Sandbox preflight requires exactly one owned snapshot slot. Its snapshot/archive identity and bounded counts enter the idempotency fingerprint, protected payload and SQLite submission ledger.
7. Confirmation reads and authenticates the bound archive, verifies ledger/payload identity, materializes it into a new temporary directory, verifies every file SHA/length, and deletes that directory after the gateway call.
8. Success creates only a compact `agent.project-snapshot-evidence` Artifact and deletes the bound encrypted snapshot with the protected payload. Failure retains both under the existing bounded investigation policy.
9. The process-global workspace root remains only a direct/development compatibility path. Governed service submission cannot use it because the boundary requires `project_snapshot_id` for the Sandbox Agent.

## Recurrence gates

- traversal, symlink, case collision and size-bound rejection tests;
- encrypted store round-trip, ciphertext tamper rejection and no-plaintext check;
- temporary materialization hash verification and cleanup test;
- missing snapshot rejection for the Sandbox Agent;
- snapshot rejection for non-Sandbox Agents;
- cross-principal snapshot slot returns 404;
- snapshot identity changes the submission request fingerprint;
- upload → preflight → confirm → execution vertical test;
- compact evidence Artifact contains hashes/counts and no raw archive/host path/file list;
- successful execution deletes the bound snapshot;
- full Python, Node, reference and fresh-ZIP acceptance.
