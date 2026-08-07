# WORKSPACE-ISSUE-038 — Runtime persistence ports and governed admission transaction ownership were not explicit

## Observed boundary

STEP091A proved that direct PostgreSQL implementation was unsafe because the existing code had two different levels of abstraction:

- `ProductStore` exposed concrete domain operations;
- most other persistence Protocols accepted `*args: Any, **kwargs: Any`;
- `SQLiteRunSubmissionStore.create_governed_task_run()` directly owned Product Task/Run/Event and Submission binding atomicity;
- Bootstrap independently constructed concrete SQLite and local-file implementations.

The existing implementation was locally correct, but its transaction owner was implicit in one adapter and not represented in the application port model.

## Risk

A direct PostgreSQL port could have produced:

- separate Product and Submission transactions;
- a committed Run without a bound Submission;
- a bound Submission without the initial Run Event;
- different repositories claiming ownership of retry/idempotency behavior;
- application code continuing to name SQLite-specific implementations;
- a mixed storage topology assembled without validation.

## Closure

STEP091B1 introduces:

```text
RunSubmissionStorePort
GovernedRunAdmissionPort
StorageTopology
SQLiteStorageTopologySettings
build_sqlite_storage_topology
```

`SQLiteRunSubmissionStore` implements both ledger and admission ports. The topology factory validates that both roles are the same object and records the exact transaction owner identifier:

```text
sqlite-run-submission-governed-admission-v1
```

Session and Evaluation application contracts now depend on backend-neutral ports. PostgreSQL and Artifact blob storage remain explicitly unimplemented.

## Prevention

- A new persistence backend must implement the typed Protocols.
- Governed admission cannot be assembled from independent transaction owners.
- Bootstrap must use a validated topology factory.
- Runtime deterministic acceptance must prove PostgreSQL is not falsely claimed.
- Full Runtime regression is required after persistence boundary changes.
