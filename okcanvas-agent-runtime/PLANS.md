# OKCanvas Agent Runtime Plans

```text
Current Workspace: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Workspace Version: 0.8.4-r7a1
Current Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime Version: 2.75.0
State: RUNTIME_PRODUCT_UNCHANGED_STEP091D_OBJECT_STORAGE_LIVE_PENDING
Promotion: NOT_READY_AT_WORKSPACE_R7A1
```

## Current Runtime baseline

The Runtime remains STEP091D / 2.75.0. STEP008R4R7A1 is a Workspace-only Git repository hygiene
correction and does not change Runtime Product code. R7A's current-document SOT correction remains
retained.

Completed Runtime scope retained from STEP091D:

- STEP091C SDK-neutral Artifact Blob Store boundary;
- S3-compatible boto3 deployment client and environment composition;
- isolated-prefix real Object Storage live gate implementation;
- parent STEP091B3R1 PostgreSQL Product/Submission/Approval/Evaluation/Session metadata topology;
- encrypted local SQLite SDK Session history;
- `sqlite-local-v1` and local filesystem Artifact storage as defaults.

## Current execution status

```text
Parent STEP091D deterministic/Fresh evidence     retained historical evidence
Parent real PostgreSQL                           19/19 PASSED
Real MinIO/S3-compatible Object Storage           DEFERRED_BY_USER
Current R7A1 tests                                NOT_EXECUTED_BY_USER_DIRECTION
```

Do not describe real PostgreSQL acceptance as pending. Do not claim Object Storage live acceptance
until the dedicated STEP091D gate is actually executed against MinIO/S3-compatible storage.

## Next Runtime-affecting work

MinIO-independent Workspace production boundaries currently rank ahead of new Artifact lifecycle
work: physical Admin/Service network isolation and a versioned PostgreSQL migration lifecycle.

After MinIO live evidence is accepted, re-audit and then consider Artifact inventory/quarantine/GC.
For future Worker scaling, extend the existing durable claim/expiry/recovery ledger with physical
Worker heartbeat/lease renewal; do not create a second claim system.
