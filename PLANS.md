# OKCanvas Agent Platform Plans

```text
Current Workspace: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Workspace Version: 0.8.4-r7a1
Current Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime Version: 2.75.0
State: IMPLEMENTED_STATIC_VALIDATED_TEST_EXECUTION_DEFERRED_BY_USER_MINIO_PENDING
Promotion: NOT_READY
MinIO/Object Storage Live: DEFERRED_BY_USER
```

## Current corrective closure

STEP008R4R7A1 adds Git repository metadata without changing Runtime Product semantics. It retains
R7A's current-document SOT correction and closes the fresh-repository ignore conflict recorded as
`WORKSPACE-ISSUE-041` and the full-tree unanchored-ignore collision recorded as `WORKSPACE-ISSUE-042`.

```text
R7A current-document SOT correction              RETAINED
Root .gitattributes                               IMPLEMENTED
Root .gitignore hygiene                          IMPLEMENTED
Runtime retained clients/cli/dist tracking       IMPLEMENTED
Fresh Git ignore/attribute sentinel checks       STATIC_VALIDATED
Unit / deterministic / live tests                DEFERRED_BY_USER_UNTIL_MINIO_READY
Promotion                                         NOT_READY
```

## Current production-gap ordering

MinIO-independent work after this corrective candidate is accepted:

1. Admin / Service listener physical isolation.
2. Versioned PostgreSQL migration lifecycle.
3. Dependency-aware `/livez` / `/readyz` boundary.
4. Service credential expiry/revocation/rotation lifecycle.

MinIO-dependent sequence:

1. STEP091D real Object Storage isolated-prefix live acceptance.
2. Artifact blob inventory + global metadata inventory.
3. age threshold + quarantine/recheck + idempotent orphan GC.
4. only then pin required S3 retry/timeout/TLS/encryption policies from observed deployment needs.

Scale/Product candidates remain later: physical Worker + heartbeat/lease renewal using the existing
claim ledger, distributed Session history/HA, governed Groupware write, durable Automation, and
Product UI/Skill Platform V2.

Do not select a new implementation merely from this list without checking the then-current code.
