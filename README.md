# OKCanvas Agent Platform Workspace

```text
Current Workspace: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Workspace Version: 0.8.4-r7a1
Current Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime Version: 2.75.0
State: IMPLEMENTED_STATIC_VALIDATED_TEST_EXECUTION_DEFERRED_BY_USER_MINIO_PENDING
Promotion: NOT_READY
Parent candidate: STEP008R4R7A / STEP091D
```

STEP008R4R7A1 is a Workspace-only Git repository hygiene correction on top of R7A. It does not
change Runtime Product behavior or the STEP091D / 2.75.0 Runtime identity. It adds deterministic
Git line-ending policy, strengthens local/generated-file exclusions, and closes the nested Runtime
`.gitignore` conflict that hid the accepted `okcanvas-agent-runtime/clients/cli/dist/` source artifact
in a fresh repository. The fresh-repository dist conflict is recorded as `WORKSPACE-ISSUE-041`; the full-tree scan also found and records unanchored Product/vendored-source ignore collisions as `WORKSPACE-ISSUE-042`.

R7A's machine-readable current baseline and per-file current-document identity gate remain retained.
Current R7A1 unit, deterministic, Windows, Live OpenAI and Object Storage test execution is
intentionally not claimed because the user deferred test execution until MinIO is prepared.

MinIO-dependent STEP091D live acceptance remains pending. Independent next production boundaries
from the full-code audit are Admin/Service listener isolation and versioned PostgreSQL migration.

See `HANDOFF.md`, `PLANS.md`, `docs/audits/WORKSPACE_STEP008R4R7_FULL_CODE_GAP_READ_ONLY_AUDIT.md`,
`docs/plans/WORKSPACE_STEP008R4R7A_CURRENT_DOCUMENT_SOT_ALIGNMENT_AND_PER_FILE_IDENTITY_GATE.md`,
and `docs/plans/WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING.md`.
