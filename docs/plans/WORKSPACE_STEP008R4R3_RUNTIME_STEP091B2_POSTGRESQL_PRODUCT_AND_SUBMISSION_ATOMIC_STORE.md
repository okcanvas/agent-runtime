# WORKSPACE STEP008R4R3 — Runtime STEP091B2 PostgreSQL Product and Submission Atomic Store

## Baseline

```text
Parent Workspace: STEP008R4R2 / 0.8.4-r2
Parent Runtime: STEP091B1 / 2.71.0
Current Runtime: STEP091B2 / 2.72.0
```

## Scope

- Add an explicit opt-in `postgresql-hybrid-v1` Product storage topology.
- Keep `sqlite-local-v1` as the default.
- Place Product Task/Run/Event/Invocation/Artifact metadata, Submission ledger, governed admission,
  and service Task/Run ownership on one PostgreSQL DSN.
- Preserve one transaction for Task, Run, first Event, Submission binding and ownership.
- Retain local SQLite Tool Approval, Evaluation and encrypted Session history.
- Retain local filesystem Artifact binaries.

## Safety

- PostgreSQL driver loading is lazy.
- DSNs are never written to deterministic evidence.
- Submission mutation uses row locks.
- idempotency registration uses a transaction advisory lock.
- Run Event sequence allocation locks the owning Run.
- No PostgreSQL-live claim is allowed without a real server run.

## Acceptance

```text
Runtime STEP091B2 25/25
Runtime full suite exact partitions
Workspace unit tests
Connector 11/11
Example 19/19
Connector→Example 17/17
Workspace manifest drift zero
Fresh ZIP repeat
```

Windows deterministic and Live OpenAI must be rerun because Bootstrap storage selection changed.
