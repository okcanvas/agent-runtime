# STEP091B2 — PostgreSQL Product and Submission Atomic Store

## Baseline

```text
Parent Runtime: STEP091B1 / 2.71.0
Target Runtime: STEP091B2 / 2.72.0
SQLite local topology: retained as default
PostgreSQL topology: explicit opt-in
Artifact blobs: local filesystem retained
Session/Evaluation/Approval: SQLite local retained in the hybrid topology
API/Worker separation: not implemented
Distributed lease: not implemented
```

## Proven boundary

STEP091B1 established typed persistence ports and explicit governed-admission transaction ownership.
STEP091B2 adds PostgreSQL only for the state that must share one transaction boundary:

```text
Product Task
Product Run
Run Event
Agent Invocation
Artifact metadata
Submission ledger
Governed Task/Run admission
Service Task/Run ownership
```

## Required semantics

1. PostgreSQL Product and Submission adapters use the same DSN and migration namespace.
2. Governed admission creates Task, Run, first Event, Submission binding and optional ownership in one
   database transaction.
3. Run-event sequence allocation is serialized by locking the owning Run row.
4. Submission mutation and execution claims lock the Submission row before state transition.
5. SQLite remains the default and its behavior must not change.
6. PostgreSQL driver loading is lazy; SQLite deployments do not require the driver at import time.
7. Bootstrap admits PostgreSQL only through a validated storage topology.
8. A supplied DSN must never be emitted in Runtime evidence or errors.

## Configuration

```text
OKCANVAS_PRODUCT_STORE_BACKEND=sqlite-local-v1 | postgresql-hybrid-v1
OKCANVAS_POSTGRESQL_DSN=<secret DSN>
```

The PostgreSQL topology keeps Evaluation and Session storage local in this step. Tool Approval remains
local SQLite. Service ownership moves with Product and Submission because governed admission writes
Task/Run ownership atomically.

## Explicit exclusions

- Object Storage / ArtifactBlobStorePort
- PostgreSQL Session history
- PostgreSQL Evaluation store
- PostgreSQL Tool Approval store
- multi-node Worker claim and heartbeat
- distributed Scheduler or Recovery Controller
- schema downgrade

## Acceptance

```text
PostgreSQL SQL compatibility contract
DSN redaction contract
atomic governed admission contract
Run Event sequence lock contract
Submission row lock contract
SQLite topology regression
PostgreSQL hybrid topology validation
Bootstrap backend selection
Architecture validation
focused regression
full Runtime exact partitions
Fresh package validation
```
