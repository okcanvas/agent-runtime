# STEP091C Artifact Blob Store and Object Storage Boundary

## Identity

```text
STEP=STEP091C_ARTIFACT_BLOB_STORE_AND_OBJECT_STORAGE_BOUNDARY
VERSION=2.73.0
PARENT=STEP091B2_POSTGRESQL_PRODUCT_AND_SUBMISSION_ATOMIC_STORE / 2.72.0
```

## Purpose

Separate durable Artifact metadata from Artifact binary storage without weakening the accepted Product Task/Run/Event/Artifact ledger.

## Implemented

- `ArtifactBlobStorePort` with typed `put/read/verify/delete/exists` operations.
- `ArtifactService` as the sole application coordinator of blob persistence and Product metadata registration.
- Opaque `local-artifact-v1://` references for local filesystem blobs.
- SDK-neutral `object-artifact-v1://` Object Storage adapter through `ObjectStorageClient`.
- ProductStore metadata registration using `storage_ref`, SHA-256 and byte length; ProductStore no longer opens Artifact files.
- Execution, approval-resume, Admin, Service and recorded evaluation paths use `ArtifactService`.
- Metadata registration failure compensates a previously written blob by deletion.
- Both SQLite and PostgreSQL hybrid storage topologies own one Artifact blob store.

## Retained

- SQLite remains the default Product storage topology.
- PostgreSQL Product/Submission atomic storage from STEP091B2 is unchanged.
- Tool Approval, Evaluation and Session persistence remain local.
- Artifact binary default remains local filesystem.
- Organization Context, Router, Agents, Skills, MCP Tools, Connector and Example semantics are unchanged.

## Explicit limitations

- No real S3, Azure Blob, GCS or MinIO server was executed.
- No provider SDK is bundled; Object Storage is injected through a client protocol.
- Object Storage environment bootstrap requires a real client integration in a deployment composition root.
- Blob garbage collection and orphan inventory are not implemented in this Step.
- Multi-node worker leasing and distributed Artifact commit protocol are not implemented.

## Acceptance

- STEP091C deterministic gate: 26/26.
- Architecture: 40/40.
- Focused regression: 88/88.
- Full Runtime suite and Workspace/Fresh ZIP gates are required before packaging promotion.
