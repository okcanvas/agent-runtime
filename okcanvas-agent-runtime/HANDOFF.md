# OKCanvas Agent Runtime HANDOFF

```text
Current Workspace: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Workspace Version: 0.8.4-r7a1
Current Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime Version: 2.75.0
State: RUNTIME_PRODUCT_UNCHANGED_STEP091D_OBJECT_STORAGE_LIVE_PENDING
Promotion: NOT_READY_AT_WORKSPACE_R7A1
```

## Runtime status

Runtime Product identity remains `STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE / 2.75.0`.
STEP008R4R7A1 changes Workspace Git metadata/governance surfaces only. It does not introduce a new
Runtime Product Step. The nested Runtime `.gitignore` now explicitly re-includes the retained
`clients/cli/dist/` artifact for fresh Git repositories.

STEP091D retains:

```text
ArtifactBlobStorePort                    retained
ObjectStorageArtifactBlobStore           retained
S3-compatible boto3 deployment client    implemented
Environment composition                  implemented
Default Artifact backend                 local-filesystem-artifact-v1
Default Product topology                 sqlite-local-v1
Real Object Storage live                 DEFERRED until MinIO is prepared
```

Parent STEP091B3R1 real PostgreSQL acceptance remains historical and accepted 19/19.

## Current-document SOT correction

The full-code audit found this Runtime HANDOFF/README were current but `PLANS.md` was stale at
STEP091B3R1. Current identity is now centralized in `../specs/workspace/current-baseline.json` and
all three Runtime current documents carry the same exact Workspace/Runtime marker block.

Historical STEP091B3R1/STEP091C/STEP091D evidence files keep their original identity and must not be
bulk-rewritten to the newest Workspace corrective Step.

## Retained Product-owned capability identities

```text
Product-owned Skill package     document-review-v1
Function Tool                   local_text_fingerprint
Function Tool                   local_text_metrics
Function Tool                   project_readonly_inspect
Function Tool                   sandbox_project_readonly_inspect
Reference capability            reference-catalog
Organization Context Connector  organization-context-read
Groupware Connector boundary    groupware-read
Groupware deployment mode       external-connector-service
Groupware Connector project     okcanvas-connectors/groupware-mcp-server
Groupware Example class         EXAMPLE_TEMPLATE_ONLY
```

## Open implementation boundaries

```text
MinIO/Object Storage live         DEFERRED_BY_USER
Artifact orphan inventory / GC    NOT_IMPLEMENTED
Production DB migration           NOT_IMPLEMENTED
Distributed Session history       NOT_IMPLEMENTED
API/Worker physical split         NOT_IMPLEMENTED
Worker heartbeat/lease renewal    NOT_IMPLEMENTED
Distributed Worker lease          NOT_IMPLEMENTED
```
