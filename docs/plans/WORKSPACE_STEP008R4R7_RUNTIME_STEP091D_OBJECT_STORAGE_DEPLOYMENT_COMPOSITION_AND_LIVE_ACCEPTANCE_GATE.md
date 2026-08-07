# WORKSPACE STEP008R4R7 Runtime STEP091D Object Storage Deployment Composition and Live Acceptance Gate

```text
Workspace: WORKSPACE_STEP008R4R7_RUNTIME_STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Workspace version: 0.8.4-r7
Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime version: 2.75.0
Parent promoted Workspace: STEP008R4R6 / 0.8.4-r6
Parent promoted Runtime: STEP091B3R1 / 2.74.1
```

## Selection evidence

The required post-PostgreSQL READ_ONLY audit was completed before implementation. It rejected both
large candidate waves as the immediate next step:

- Artifact orphan inventory/GC is missing, but depends on a deployment Object Storage path that had
  never been composed or run live.
- API/Worker physical separation is larger than previously summarized because durable claim,
  expiry and recovery state already exists; the missing part is a physical Worker plus heartbeat /
  renewal semantics that must extend, not duplicate, that ledger.

The smaller prerequisite found in code is STEP091C's deployment gap: `app_from_environment()` could
select `object-storage-artifact-v1` but never supplied `object_storage_client`, causing composition to
fail. STEP091D closes that exact boundary.

## Workspace contract additions

```text
artifact_object_storage_environment_composition = true
artifact_object_storage_client = s3-compatible-boto3-v1
artifact_object_storage_live_gate_implemented = true
artifact_object_storage_live_gate = real-s3-compatible-isolated-prefix-v1
artifact_object_storage_live_confirmation_env = OKCANVAS_OBJECT_STORAGE_LIVE_CONFIRM
artifact_object_storage_live_confirmation_value = CREATE_AND_DELETE_ISOLATED_TEST_PREFIX
artifact_object_storage_live_accepted = false
```

## Retained accepted evidence

```text
Parent Windows deterministic        33/33 PASSED
Parent Windows Live OpenAI          29/29 PASSED
Real PostgreSQL                     19/19 PASSED
PostgreSQL server_version_num       180004
```

Those are parent baseline facts. R7 requires its own Windows deterministic / Live OpenAI regression
before promotion because Runtime source changes in STEP091D.

## Current deterministic requirements

```text
Runtime STEP091D deterministic      19/19
Architecture                        40/40
Runtime full suite                  251 files / 1,047 tests / 18 exact partitions
Workspace tests                     all pass
Connector                           11/11
Example                             19/19
Connector -> Example                17/17
Workspace manifest drift            0
```

## Real Object Storage live gate

The gate is fail-closed and uses an existing bucket. It creates only randomized object keys under
one isolated prefix and deletes every known object in `finally` cleanup. It never creates or deletes
the bucket.

```text
Required bucket:       OKCANVAS_ARTIFACT_OBJECT_BUCKET
Required confirmation: OKCANVAS_OBJECT_STORAGE_LIVE_CONFIRM
Exact value:            CREATE_AND_DELETE_ISOLATED_TEST_PREFIX
Credentials:            standard boto3/AWS credential chain
```

## Promotion boundary

`artifact_object_storage_live_accepted` remains false until the dedicated live gate runs against an
actual S3 or S3-compatible server and passes. Local/Fresh deterministic acceptance cannot make that
claim. Current R7 promotion also requires its Windows deterministic and Windows Live OpenAI
regression gates.

## Explicit non-goals

- bucket provisioning/deletion;
- Artifact orphan inventory or garbage collection;
- production DB migration;
- distributed Session history;
- API/Worker physical separation;
- Worker heartbeat/lease renewal or distributed Worker lease.

## Local implementation acceptance result

```text
Runtime STEP091D                 19/19 PASSED
Architecture                     40/40 PASSED
Runtime full suite               251/251 files / 1,047/1,047 PASSED
Runtime partitions               18/18 exact
Workspace unit tests             131/131 PASSED
Workspace aggregate              34/34 PASSED
Connector                        11/11 PASSED
Example                          19/19 PASSED
Connector -> Example             17/17 PASSED
Workspace manifest drift         0
Fresh ZIP                        PENDING
Real Object Storage              NOT_EXECUTED
Promotion                        NOT_READY
```
