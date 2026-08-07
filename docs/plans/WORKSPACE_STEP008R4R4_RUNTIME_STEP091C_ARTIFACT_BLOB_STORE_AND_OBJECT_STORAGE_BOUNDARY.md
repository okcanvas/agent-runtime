# WORKSPACE STEP008R4R4 — Runtime STEP091C Artifact Blob Store Boundary

## Identity

```text
Workspace: WORKSPACE_STEP008R4R4_RUNTIME_STEP091C_ARTIFACT_BLOB_STORE_AND_OBJECT_STORAGE_BOUNDARY
Version: 0.8.4-r4
Runtime: STEP091C_ARTIFACT_BLOB_STORE_AND_OBJECT_STORAGE_BOUNDARY
Runtime version: 2.73.0
```

## Objective

Integrate STEP091C without changing Organization Context routing, Agent, Skill, MCP, Connector or
Example semantics. Validate that Artifact metadata and binary persistence are distinct boundaries,
that all Product read/write paths use ArtifactService, and that the Object Storage adapter remains
SDK-neutral and explicit opt-in.

## Product changes

- Typed `ArtifactBlobStorePort`.
- `ArtifactService` coordinates binary and metadata persistence.
- Local and Object Storage opaque references.
- Blob compensation on metadata-registration failure.
- Bootstrap-owned Artifact backend selection.
- ProductStore metadata-only Artifact registration.

## Explicit limitations

- No real Object Storage server execution.
- No Artifact inventory/garbage collection.
- No API/Worker split.
- No distributed lease.
- No new Organization Context execution semantics.

## Acceptance

- Runtime STEP091C 26/26.
- Architecture 40/40.
- Runtime full suite 248/248 files and 1,034/1,034 tests.
- Workspace tests and deterministic gate.
- Connector 11/11, Example 19/19, Connector→Example 17/17.
- Fresh ZIP manifest exact and zero post-acceptance drift.
- Windows deterministic and Live remain pending until user execution.
