# OR-ISSUE-109 — Persistence ports did not declare governed admission transaction ownership

## Symptom

The Runtime appeared storage-pluggable because `ProductStore` and several application ports existed,
but PostgreSQL could not safely replace SQLite one adapter at a time.

## Root cause

- `SQLiteRunSubmissionStore` directly wrote Product Task/Run/Event tables to preserve atomic
  governed admission.
- `RunSubmissionStorePort` mixed Submission ledger operations with Product admission.
- Other persistence ports used broad variadic `Any` signatures.
- Application contracts named SQLite Session and Evaluation implementations.
- Bootstrap had no topology invariant requiring Submission and admission to share one transaction
  owner.

## Risk

A table-for-table PostgreSQL port could pass CRUD tests while allowing partial states such as:

```text
Submission bound but Run absent
Run created but run.created Event absent
Task/Run created but service ownership absent
```

## Correction

STEP091B1:

- added exact typed persistence protocols;
- split `GovernedRunAdmissionPort` from `RunSubmissionStorePort`;
- injected the admission dependency into read-only and approval execution services;
- added a validated SQLite storage topology bundle;
- retained the existing SQLite transaction as the only current admission implementation;
- added contract and regression tests.

## Prevention

Before adding a persistence backend:

1. identify same-transaction invariants;
2. assign one explicit transaction owner;
3. define typed input/output/concurrency contracts;
4. prove existing backend conformance;
5. run the same semantic tests against every backend.

Do not infer backend interchangeability from matching table names or CRUD methods.
