# STEP091D Object Storage Deployment Composition and Live Acceptance Gate

```text
STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Version: 2.75.0
Parent promoted Runtime: STEP091B3R1 / 2.74.1
```

## Objective

Close the smallest storage boundary found by the post-STEP091B3R1 READ_ONLY audit: STEP091C had an
SDK-neutral Object Storage blob adapter, but the normal environment composition root never
constructed its deployment client. `object-storage-artifact-v1` therefore was not deployable through
`app_from_environment()`.

STEP091D adds deployment composition and a bounded real-server gate without changing the generic
Artifact port or the default local backend.

## Implementation

- `Boto3S3CompatibleObjectStorageClient` adapts boto3 to the retained `ObjectStorageClient` protocol.
- `S3CompatibleClientSettings` owns endpoint, region and addressing style only.
- credentials remain in boto3's standard credential chain; access/secret keys are not copied into
  Runtime settings or evidence.
- `app_from_environment()` constructs the deployment client only when
  `OKCANVAS_ARTIFACT_BLOB_STORE_BACKEND=object-storage-artifact-v1`.
- `boto3` is an optional `object-storage` dependency, so the default local installation remains
  independent of an Object Storage SDK.
- `local-filesystem-artifact-v1` remains the Artifact default.

## Live safety boundary

```text
OKCANVAS_OBJECT_STORAGE_LIVE_CONFIRM=CREATE_AND_DELETE_ISOLATED_TEST_PREFIX
OKCANVAS_ARTIFACT_OBJECT_BUCKET=<existing bucket>
```

Optional endpoint/region/addressing configuration supports AWS S3 and S3-compatible services such
as MinIO. The gate creates only keys below a randomized STEP091D prefix. Bucket creation/deletion is
outside the gate.

## Live contracts

- actual S3-compatible client construction;
- Artifact put + Product metadata persistence;
- JSON get round-trip;
- HEAD integrity metadata;
- storage-reference scope fence;
- metadata-registration failure compensates the already-written object;
- object delete/absence;
- local filesystem backend remains available;
- known objects under the isolated prefix are deleted during final cleanup;
- raw credential values are never written to evidence.

## Deterministic acceptance

```text
STEP091D deterministic       19/19 PASSED
Architecture                 40/40 PASSED
Focused regression           35/35 PASSED
Full Runtime test files      251/251
Full Runtime tests           1,047/1,047 PASSED
Partitions                   18/18 exact
Failed / skipped             0 / 0
Missing / duplicate files    0 / 0
```

## Retained parent evidence

STEP091B3R1 real PostgreSQL remains 19/19 accepted. SQLite remains the Product default and encrypted
SDK Session conversation history remains local SQLite.

## Live status

```text
Real Object Storage server   NOT_EXECUTED
Object Storage live accepted false
Bucket provisioning          NOT_EXECUTED
```

## Not implemented or claimed

- Artifact orphan inventory / GC;
- API/Worker physical split;
- Worker heartbeat/lease renewal;
- distributed Worker lease;
- distributed Session history;
- production DB migration.
