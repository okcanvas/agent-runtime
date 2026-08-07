# STEP091B3 PostgreSQL Approval, Evaluation and Session Metadata

```text
STEP091B3_POSTGRESQL_APPROVAL_EVALUATION_AND_SESSION_METADATA
Version: 2.74.0
Parent: STEP091C / 2.73.0
```

## Objective

Extend the explicit `postgresql-hybrid-v1` topology without changing the default
`sqlite-local-v1` topology. Product Tool Approval, Evaluation and Product Session
lifecycle metadata move to PostgreSQL on the same DSN already used by Product,
Submission and Service ownership. Encrypted SDK Session history remains in the
existing local SQLite history store.

## Implemented boundary

```text
PostgreSQL DSN
├─ Product Task / Run / Event / Invocation / Artifact metadata
├─ Submission ledger and governed admission
├─ Service Task/Run ownership
├─ Tool Approval state and resume fencing
├─ Evaluation results, suites and baselines
└─ Session lifecycle metadata
   ├─ active Run fencing
   ├─ turn/item counts
   └─ key-rotation checkpoint metadata

Local encrypted storage
└─ SDK Session history binary rows
```

## Atomicity and concurrency

- Tool Approval keeps the inherited Product state machine and uses the same PostgreSQL
  transaction domain as Task, Run, Submission and Run Event.
- Approval and Session rows are selected with transaction-scoped row locking.
- Run Event sequence ownership remains locked by the owning Run row.
- Every PostgreSQL metadata adapter in one topology must expose the same DSN digest.
- Session history is not represented as distributed; only metadata is PostgreSQL-owned.

## Not implemented or claimed

- Real PostgreSQL server acceptance
- Production database migration
- Distributed Session history
- Cross-node Session history access
- Object Storage live acceptance
- API/Worker split
- Distributed Worker lease

## Acceptance

```text
STEP091B3 deterministic      22/22 PASSED
Architecture                 40/40 PASSED
Focused regression           115/115 PASSED
Full Runtime                 249/249 files, 1,038/1,038 tests PASSED
```
