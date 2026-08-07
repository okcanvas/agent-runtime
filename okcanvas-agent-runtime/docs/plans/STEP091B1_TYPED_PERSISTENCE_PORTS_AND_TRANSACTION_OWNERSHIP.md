# STEP091B1 — Typed Persistence Ports and Transaction Ownership

## Baseline

```text
Parent Runtime: STEP090R1 / 2.70.1
Current Runtime: STEP091B1 / 2.71.0
Storage backend retained: SQLite local
Behavior change: none intended
PostgreSQL: not implemented
Artifact blob storage: not implemented
Distributed Worker lease: not implemented
```

## Problem proven by STEP091A

The existing Runtime already had strong Task/Run/Event semantics, but persistence replacement was unsafe:

1. `SQLiteRunSubmissionStore.create_governed_task_run()` directly owned Product `task`, `run`,
   `run_event`, Submission binding, and optional ownership rows in one SQLite transaction.
2. Most application persistence ports used `*args: Any, **kwargs: Any` and did not define portable
   input, output, conflict, or concurrency contracts.
3. Application and Gateway types named `SQLiteSessionRuntimeService` directly.
4. Evaluation application services named `SQLiteEvaluationStore` directly.
5. Bootstrap assembled independently valid stores without one topology contract proving that the
   Submission ledger and Product admission transaction owner were the same backend unit.

A direct PostgreSQL adapter would therefore risk preserving CRUD while breaking governed admission.

## Implemented boundary

### Typed ports

`application/ports/stores.py` now defines explicit protocols for:

- Run Submission ledger;
- governed Run admission;
- protected payload;
- attachments;
- project snapshots;
- Run state;
- Tool Approval;
- service resource ownership;
- evaluation persistence;
- Session Runtime.

Public persistence methods no longer use variadic `Any` signatures.

### Governed admission ownership

`GovernedRunAdmissionPort` owns exactly this atomic contract:

```text
confirmed Submission
→ Task READY
→ Run CREATED
→ run.created Event
→ Submission Task/Run binding
→ optional service Task/Run ownership
```

`RunSubmissionStorePort` no longer declares this operation. The current SQLite adapter structurally
implements both ports because it remains the one transaction owner.

`GovernedReadOnlyRunSubmissionService` and `GovernedLocalToolApprovalService` receive an explicit
admission dependency and invoke it for Product Task/Run creation.

### Validated storage topology

`bootstrap/storage_topology.py` introduces:

```text
StorageTopology
SQLiteStorageTopologySettings
build_sqlite_storage_topology()
```

The SQLite topology validates:

- schema `okcanvas-storage-topology-v1`;
- backend `sqlite-local-v1`;
- transaction owner `sqlite-run-submission-governed-admission-v1`;
- Submission ledger and governed admission are the same object.

Bootstrap exposes the validated topology and governed admission through `app.state`.

### Concrete dependencies removed from application types

- Session execution/application/Gateway contracts use `SessionRuntimePort`.
- Evaluation application/suite contracts use `EvaluationStorePort`.
- ServiceUseCases types Product, Submission, Approval, Ownership, Session, Attachment and Snapshot
  persistence through ports.

## Retained semantics

- SQLite remains the only admitted backend.
- Existing SQLite schema and transaction body are retained.
- Product transition guards are unchanged.
- Artifact files remain local filesystem-backed.
- Session mode remains `sqlite-v1` for compatibility.
- No API, Agent, Tool, MCP, Skill, model, retry, payload, or output-contract behavior changes.

## Acceptance

Required:

```text
STEP091B1 deterministic acceptance 25/25
Architecture validation 40/40
Focused persistence regression
Full Runtime exact non-overlapping partitions
SQLite governed admission atomicity retained
Launcher registry current records exact
Compileall
Fresh package validation
```

## Next admitted step

```text
STEP091B2_POSTGRESQL_PRODUCT_AND_SUBMISSION_ATOMIC_STORE
```

The PostgreSQL implementation must use one migration/transaction unit for Product Task/Run/Event,
Submission binding, and optional Task/Run ownership. Remaining adapters and Artifact blobs stay out
of STEP091B2 unless their exact contract is needed for that transaction.
