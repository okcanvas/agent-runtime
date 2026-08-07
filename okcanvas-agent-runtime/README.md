# OKCanvas Agent Runtime

```text
Current Workspace: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Workspace Version: 0.8.4-r7a1
Current Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime Version: 2.75.0
State: RUNTIME_PRODUCT_UNCHANGED_STEP091D_OBJECT_STORAGE_LIVE_PENDING
Promotion: NOT_READY_AT_WORKSPACE_R7A1
```

The Runtime remains STEP091D / 2.75.0. STEP008R4R7A1 changes Workspace Git repository metadata and
current governance only; it does not change `okcanvas_agent_runtime/**` Product behavior. R7A's
current-document SOT correction remains retained.

STEP091D provides S3-compatible boto3 deployment composition for the SDK-neutral
`ObjectStorageArtifactBlobStore` and a fail-closed real Object Storage live gate over a randomized
prefix in an existing bucket. `local-filesystem-artifact-v1` and `sqlite-local-v1` remain defaults.

Parent real PostgreSQL STEP091B3R1 remains accepted 19/19. MinIO/Object Storage live execution is
explicitly deferred until MinIO is prepared. Artifact GC, production DB migration, distributed
Session history, API/Worker physical split and distributed Worker lease remain unclaimed.

Current Workspace/Runtime identity is owned by `../specs/workspace/current-baseline.json` and each
current Runtime document is independently checked by `../scripts/validate_current_document_sot.py`.
