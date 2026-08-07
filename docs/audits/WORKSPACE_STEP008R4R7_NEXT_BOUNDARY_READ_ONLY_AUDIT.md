# WORKSPACE STEP008R4R7 Next Boundary READ_ONLY Audit

## Baseline

- Workspace: `WORKSPACE_STEP008R4R6_RUNTIME_STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE` / `0.8.4-r6`
- Runtime: `STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE` / `2.74.1`
- Promotion: current promoted baseline
- Audit mode: READ_ONLY against the promoted source before STEP091D implementation.

## Code findings

### Artifact orphan inventory / garbage collection

`ArtifactService.create_bytes()` writes the blob first and compensates metadata-registration failure with `blob_store.delete()`. The `ArtifactBlobStorePort` already has `delete()` and `exists()` but has no inventory/list operation, object age, or quarantine/retention contract. Long-lived orphan discovery and garbage collection are therefore not implemented.

This is a real missing lifecycle boundary, but it builds on a deployment storage backend that has not yet been proven live.

### API / Worker physical separation

The governed Submission ledger already contains `claim_owner_id`, claim token hash, acquired/expiry timestamps, attempt and recovery counters. `claim_execution()`, `execution_fence_active()`, stale pre-start recovery, orphaned RUNNING reconciliation, and terminal-outcome reconciliation are implemented.

However, execution is still owned by `LocalExecutionCoordinator` in the API process. The lifecycle policy explicitly rejects `distributed_worker_lease_enabled=true`, no Worker heartbeat/lease-renewal operation exists, and no physical Worker process consumes durable work.

Therefore the future Worker Step must extend the existing claim model rather than reimplement it.

### Smaller prerequisite found: Object Storage deployment composition

STEP091C implemented the SDK-neutral `ObjectStorageArtifactBlobStore`, but its own plan states that no real S3/Azure/GCS/MinIO server was executed and that a real client integration is required in a deployment composition root.

The current `app_from_environment()` reads:

- `OKCANVAS_ARTIFACT_BLOB_STORE_BACKEND`
- `OKCANVAS_ARTIFACT_OBJECT_BUCKET`
- `OKCANVAS_ARTIFACT_OBJECT_PREFIX`

but never constructs or injects `object_storage_client`. `create_app()` rejects `object-storage-artifact-v1` when the client is missing. Consequently the Object Storage backend cannot be selected through the normal environment deployment entrypoint.

## Decision

The next smallest closed boundary is **Object Storage deployment composition + explicit real-server Live acceptance gate**.

Artifact orphan inventory/GC remains next-after-live candidate. API/Worker physical separation remains a later, larger boundary because it requires heartbeat/renewal plus a physical Worker process and must reuse the existing claim/recovery ledger.

## Selected Step

`STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE` / `2.75.0`

Workspace integration: `WORKSPACE_STEP008R4R7_RUNTIME_STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE` / `0.8.4-r7`.
