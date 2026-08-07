# OKCanvas Agent Platform HANDOFF

```text
Current Workspace: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Workspace Version: 0.8.4-r7a1
Current Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime Version: 2.75.0
State: IMPLEMENTED_TEST_EXECUTION_DEFERRED_BY_USER_MINIO_PENDING
Promotion: NOT_READY
Parent Workspace candidate: WORKSPACE_STEP008R4R7_RUNTIME_STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE / 0.8.4-r7
Parent Runtime candidate: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE / 2.75.0
Parent promoted baseline: STEP008R4R6 / STEP091B3R1
```

## Why STEP008R4R7A1 exists

Git repository metadata was requested for publishing the Workspace as a fresh Git repository. Code-level inspection found that the root `.gitignore` intended `okcanvas-agent-runtime/clients/cli/dist/` to remain committed, but the nested Runtime `.gitignore` still contained a recursive `dist/` rule. In a fresh repository, `git add .` therefore omitted an accepted Runtime source artifact.

R7A1 adds a root `.gitattributes`, strengthens the root `.gitignore`, and adds an explicit Runtime negation for the retained CLI dist. No Runtime Product source is changed.

```text
Root .gitattributes                 deterministic LF policy
Accepted CRLF CMD exceptions        4 retained launchers
Root .gitignore                     local secrets/cache/build/state only
Runtime clients/cli/dist            explicitly TRACKABLE
Runtime docs/evidence/*.log         TRACKABLE
Runtime .env.local                  IGNORED
Runtime Product source              unchanged
Tests                               deferred until MinIO is prepared
```

The retained-dist recurrence is recorded as `WORKSPACE-ISSUE-041`. A full-tree fresh Git scan additionally found unanchored `artifacts/` and `.vscode/` rules hiding accepted Product/vendored files; that class is recorded as `WORKSPACE-ISSUE-042`.

## R7A1 static Git/package validation

```text
Git ignore sentinels                 13/13 expected semantics
Git attribute sentinels              8/8 expected semantics
Runtime retained clients/cli/dist    TRACKABLE
Runtime Product **/artifacts/**       TRACKABLE
Retained upstream .vscode files      TRACKABLE
Durable docs/evidence/*.log          TRACKABLE
Runtime .env.local                   IGNORED
Runtime .env.local.example           TRACKABLE
Current-document SOT                 7/7 PASSED
First-party Python AST               977 files / 0 failures
First-party JSON parse               847 files / 0 failures
Runtime Product                      351 files / byte-identical to parent R7A
Runtime parent manifest              4,284 files
Workspace manifest expected          4,728 canonical files
Package files expected               4,729
Unit/deterministic/live tests        NOT EXECUTED BY USER DIRECTION
```

These are static repository/package checks, not deferred acceptance-test evidence.

## Parent STEP008R4R7A correction retained

A full-code READ_ONLY audit of the immutable R7 release found a current-package SOT defect:

- root `PLANS.md` was current at STEP091D;
- `okcanvas-agent-runtime/PLANS.md` was stale at STEP091B3R1 / 2.74.1 and still described real
  PostgreSQL acceptance as pending;
- the document regression omitted the nested Runtime PLANS file and concatenated several documents
  before checking current identity, allowing a correct sibling to mask a stale document.

The recurrence is recorded as `WORKSPACE-ISSUE-040`.

## Corrective implementation

```text
Machine-readable current SOT       specs/workspace/current-baseline.json
Per-file validator                 scripts/validate_current_document_sot.py
Current Workspace scripts          identity loaded from current-baseline.json
Current document coverage          7 files, each validated independently
Historical evidence                immutable / not rewritten
Runtime Product source             unchanged by this corrective wave
Runtime identity                   STEP091D / 2.75.0 retained
```

The current document set is:

```text
README.md
HANDOFF.md
PLANS.md
okcanvas-agent-runtime/README.md
okcanvas-agent-runtime/HANDOFF.md
okcanvas-agent-runtime/PLANS.md
docs/plans/OKCANVAS_AGENT_RUNTIME_PRODUCTIZATION_MASTER_PLAN.md
```

Every file must contain exactly one marker for Current Workspace, Workspace Version, Current Runtime
and Runtime Version. The validator checks each file independently.

A regression test is included that copies the current document set, deliberately replaces the nested
Runtime PLANS current Runtime marker with the stale STEP091B3R1 value, and requires the validator to
fail. Per user direction, that regression has **not been executed yet**; it remains test-pending
until MinIO is prepared.

## Retained accepted evidence

The parent promoted R6 evidence remains historical and unchanged:

```text
Parent Windows deterministic          33/33 PASSED
Parent Windows Live OpenAI            29/29 PASSED
PostgreSQL live server: EXECUTED / 19/19 PASSED
PostgreSQL server_version_num          180004
OKCANVAS_POSTGRESQL_LIVE_DSN           operator-local; raw value not persisted
OKCANVAS_POSTGRESQL_LIVE_CONFIRM       CREATE_AND_DROP_ISOLATED_TEST_SCHEMA
```

The parent R7 local/Fresh deterministic evidence also remains historical and unchanged:

```text
STEP091D deterministic             19/19 PASSED
Architecture                       40/40 PASSED
Runtime full regression            251 files / 1,047 tests PASSED
Workspace unit tests               131/131 PASSED
Workspace aggregate                34/34 PASSED
Object Storage live server         NOT_EXECUTED
Object Storage live accepted       false
```

These parent results are not claimed as current R7A test execution.

## User-directed test hold

```text
Current R7A unit tests              NOT_EXECUTED_BY_USER_DIRECTION
Current R7A deterministic          NOT_EXECUTED_BY_USER_DIRECTION
Current R7A Windows deterministic  NOT_EXECUTED
Current R7A Windows Live OpenAI    NOT_EXECUTED
STEP091D MinIO/Object Storage live DEFERRED_UNTIL_MINIO_READY
Promotion                          NOT_READY
```

No current acceptance count or pass claim should be fabricated from parent evidence.

## Static packaging validation executed

These are source/package checks, **not deferred acceptance tests**:

```text
Current-document SOT validator        PASSED / 7 files
First-party Python AST                975 files / 0 failures
First-party JSON parse                843 files / 0 failures
Runtime Product files                 351
Runtime Product digest                c998c1623535f24b6e9543ce7086f8c339f783dd07b2d8bee2c2a34337a86265
Runtime Product changed vs source R7  NO
Historical evidence compared          975 common files / 0 changed
```

The deliberate stale nested-plan regression is present in source but is intentionally not executed
until the user resumes tests.

## Next implementation order while MinIO is pending

The full-code audit identified these independent boundaries:

1. **Admin / Service listener physical isolation** — P0 pre-production.
2. **Versioned PostgreSQL migration lifecycle** — P0 pre-production.
3. Dependency-aware liveness/readiness — P1.
4. Service credential expiry/revocation/rotation lifecycle — P1.

After MinIO is available:

1. execute STEP091D real Object Storage isolated-prefix live gate;
2. audit actual S3-compatible semantics;
3. then design Artifact inventory/quarantine/recheck/GC and explicit S3 operational hardening.

API/Worker work must extend the existing durable claim/expiry/recovery ledger; do not build a second
claim system.

## Failure / audit records

- `docs/issues/WORKSPACE-ISSUE-040-RUNTIME-PLANS-SOT-DRIFT-AND-GATE-COVERAGE-GAP.md`
- `docs/issues/STEP008R4R7A_IMPLEMENTATION_FAILURE_LOG.md`
- `docs/audits/WORKSPACE_STEP008R4R7_FULL_CODE_GAP_READ_ONLY_AUDIT.md`
- `docs/evidence/WORKSPACE_STEP008R4R7_FULL_CODE_GAP_AUDIT_SUMMARY.json`
