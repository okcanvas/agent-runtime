# STEP091A — Product Storage Boundary Exhaustive Audit

## Result

```text
MODE=READ_ONLY
PRODUCT_SOURCE_MODIFICATIONS=0
BASELINE=STEP090R1 / 2.70.1
OVERALL=IMPLEMENTATION_BOUNDARY_IDENTIFIED
POSTGRESQL_IMPLEMENTATION=NOT_ADMITTED_YET
```

## Executive conclusion

The Runtime already has strong domain semantics and several useful ports, but it is not yet a clean
storage-pluggable system. A direct SQLite-to-PostgreSQL adapter replacement would preserve some
CRUD behavior while risking the atomic governed-admission and Artifact integrity contracts.

The required first implementation is **typed port and transaction ownership closure**, not a new SQL
backend.

## Existing strengths

### ProductStore is a real domain port

`domain/runs/ports.py::ProductStore` defines Task, Run, Event, Invocation and Artifact metadata
operations. Domain transition guards remain outside SQL in `domain/runs/transitions.py` and are
reused by the SQLite adapter.

### Product state transitions are transactional

`SQLiteProductStore` uses `BEGIN IMMEDIATE`, transition validation, unique `(task_id, attempt)`,
unique `(run_id, ordinal)` and primary-keyed `(run_id, sequence)` events.

### Governed admission already has atomic local semantics

`SQLiteRunSubmissionStore.create_governed_task_run()` creates Product Task, Run, `run.created`,
Submission binding and optional service ownership in one SQLite transaction. This is an important
semantic contract that PostgreSQL must preserve.

### Payload families have explicit ports

Protected payloads, attachments, project snapshots, Run state, Tool Approval and Session Runtime
have application ports. Encryption keys and raw payloads remain outside Product Events.

## Confirmed boundary defects

### B1 — Submission adapter owns Product tables directly

`SQLiteRunSubmissionStore` directly inserts into `task`, `run` and `run_event`. It therefore depends
on `SQLiteProductStore` schema internals instead of invoking a transaction-capable Product port.
This is intentional for current atomicity, but prevents independent backend replacement.

Required correction: define one governed-admission transaction boundary implemented by the same
backend unit as Product and Submission persistence.

### B2 — Ports are weakly typed outside ProductStore

`application/ports/stores.py` exposes many methods as `*args: Any, **kwargs: Any`. This protects
imports but does not define portable behavioral contracts, record types, concurrency results or
error semantics.

Required correction: replace broad signatures incrementally with exact typed protocols and contract
tests before creating PostgreSQL adapters.

### B3 — Artifact metadata and binary ownership are mixed

`ProductStore.register_artifact()` accepts a local `Path`. `GenericAgentExecutionService` and
`GovernedLocalToolApprovalService` write JSON files directly under `artifact_root`, then ask the
Product store to inspect and register them. `ServiceUseCases` later resolves `artifact.storage_path`
and reads the file directly.

Consequences:

- ProductStore is coupled to a mounted filesystem.
- Application services own atomic file writes.
- Object storage cannot be introduced by swapping a metadata adapter.
- Metadata commit and binary availability have no explicit cross-store state machine.

Required correction: introduce an `ArtifactBlobStorePort` with staged write, hash verification,
commit/read/head/delete and orphan reconciliation semantics. Product metadata stores an opaque blob
key, not a filesystem path interpreted by application code.

### B4 — Bootstrap selects concrete storage topology

`bootstrap/application.py::create_app()` directly constructs:

- `SQLiteProductStore`;
- `SQLiteEvaluationStore`;
- `SQLiteToolApprovalStore`;
- `SQLiteServiceResourceOwnershipStore`;
- `SQLiteRunSubmissionStore`;
- `SQLiteSessionRuntimeService`;
- encrypted local payload, attachment, snapshot and Run-state stores.

This is an acceptable composition root, but there is no backend configuration object or factory
that validates a coherent topology. Independent replacement can accidentally combine stores that
cannot share required transactions.

Required correction: add a validated storage topology factory with named backend bundles.

### B5 — Cross-store operations are not generally atomic

Product, Submission, Approval, Ownership and Session adapters can use the same SQLite file but open
independent connections. Only operations deliberately implemented inside one adapter, such as
`create_governed_task_run`, are atomic across those tables. Lifecycle and Approval services perform
multi-store sequences with reconciliation rather than one database transaction.

PostgreSQL design must explicitly classify each sequence as:

- same-transaction invariant;
- idempotent multi-step workflow;
- reconciled eventual completion.

### B6 — Session capability is named as SQLite

Agent definitions and policy validation use `session_mode="sqlite-v1"`; Gateway and application
interfaces import `SQLiteSessionRuntimeService` in several places. The runtime behavior required by
Agents is encrypted durable Session with turn serialization and compaction, not SQLite as a domain
concept.

Required correction: retain `sqlite-v1` as a compatibility backend identifier while introducing a
backend-neutral Session capability/port for future database-backed Session metadata and history.

### B7 — Evaluation persistence bypasses the common port layer

`RecordedRunEvaluationService` and `EvaluationSuiteService` type directly against
`SQLiteEvaluationStore`. Evaluation is not in the critical Run admission transaction, but the
concrete dependency blocks a coherent production storage bundle.

### B8 — Local coordination is explicitly non-distributed

`LocalExecutionCoordinator` states that durable distributed leasing is deferred. Submission claims
have owner, token and expiry semantics, but scheduling is still in-process and no backend-neutral
Worker lease/heartbeat controller exists.

This must remain outside the first PostgreSQL step; storage migration must not be mislabeled as
API/Worker or HA completion.

### B9 — Schema migration ownership is fragmented

Each SQLite adapter initializes and evolves its own tables. Some adapters also rely on tables created
by another adapter. PostgreSQL requires one ordered migration set and explicit ownership of shared
constraints, indexes and foreign keys.

## Portability assessment

| Area | Current state | PostgreSQL readiness |
|---|---|---|
| Task/Run/Event/Invocation | Strong ProductStore port and domain transitions | High after transaction bundle |
| Governed Submission | Strong local semantics, schema-coupled adapter | Medium; must share Product transaction |
| Tool Approval | Port exists, exact local state machine | Medium |
| Service ownership | Concrete SQLite, use-cases typed as Any | Low–medium |
| Session metadata/history | Strong behavior, SQLite-named capability | Medium after neutral port split |
| Protected payload/attachment/snapshot | Ports and encryption exist | Medium; local file backend only |
| Artifact | Metadata and local file path mixed | Low until blob port exists |
| Evaluation | Concrete SQLite in application layer | Low–medium |
| Worker claim/HA | Local coordinator | Not part of storage migration |

## Required implementation sequence

### STEP091B1 — Typed persistence ports and transaction ownership

- Exact Product, Submission, Approval, Ownership, Evaluation and Session protocols.
- A governed-admission unit-of-work contract.
- Backend-neutral error and concurrency result types.
- Storage topology bundle validation.
- No behavior change and SQLite remains the only implementation.

### STEP091B2 — PostgreSQL Product and Submission atomic store

- One migration set for Task, Run, Event, Invocation, Artifact metadata and Submission.
- One transaction for governed Task/Run/Event/Submission/ownership admission.
- Existing Product transition and idempotency contract tests run against both backends.

### STEP091B3 — Remaining relational adapters

- Tool Approval.
- Service ownership.
- Evaluation.
- Session metadata and claim/rotation records.

### STEP091C — Artifact blob storage

- Opaque blob keys.
- Stage, verify and commit lifecycle.
- Metadata/binary orphan reconciliation.
- Local filesystem adapter first, object-store adapter second.

### Later — API/Worker split

Only after PostgreSQL semantic parity:

- durable Worker claim and heartbeat;
- lost-Worker reconciliation;
- multi-node Scheduler and Recovery ownership.

## Explicit non-goals of the next step

- No distributed lease implementation.
- No NATS/Event broker SOT.
- No object storage before ArtifactBlobStorePort.
- No rewrite of Task/Run/Event domain models.
- No replacement of encryption policy.
- No write Tool expansion.

## Final audit decision

```text
SAFE_NEXT_STEP=STEP091B1_TYPED_PERSISTENCE_PORTS_AND_TRANSACTION_OWNERSHIP
DIRECT_POSTGRESQL_PORT=REJECTED
PRODUCT_SEMANTICS_TO_RETAIN=TASK_RUN_EVENT_ARTIFACT_GOVERNED_ADMISSION
```
