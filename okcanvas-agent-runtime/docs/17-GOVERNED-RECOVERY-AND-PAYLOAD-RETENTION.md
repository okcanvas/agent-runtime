# Governed Recovery and Protected-Payload Retention

## Purpose

STEP019 closes the pre-start crash gap created by governed read-only submission without claiming active-Run or distributed recovery. It also gives encrypted request payloads a deterministic lifecycle.

## Claim generations

A confirmed submission first acquires a local execution claim. The raw generation token exists only in process memory; SQLite stores its SHA-256, owner, acquisition time, expiry time, and counters.

```text
RUN_CREATED
→ EXECUTION_CLAIMED
→ EXECUTION_SCHEDULED
→ EXECUTION_STARTED
→ EXECUTION_SUCCEEDED | EXECUTION_FAILED | EXECUTION_CANCELLED
```

A stale claim is recoverable only when:

- claim lease has expired;
- Product Task is still `READY`;
- Product Run is still `CREATED`;
- maximum claim attempts has not been reached;
- an authenticated local operator explicitly requests recovery.

Recovery atomically rotates the token generation, increments attempts/recovery count, and appends `run.execution.recovered`. The previous token then fails the guarded start transition.

## Retention policy

Canonical policy: `specs/submissions/governed-execution-lifecycle-policy.json`.

| Condition | Action |
|---|---|
| successful terminal Run | encrypted payload deleted immediately |
| failed/cancelled terminal Run | retained for seven days |
| unconfirmed submission | expires after 24 hours |
| deletion error | state `DELETE_FAILED`, operator investigation required |

Cleanup scans at most 100 eligible submissions per request. It is not an implicit background job.

## API

```text
POST /v1/run-submissions/recover-stale
POST /v1/protected-payloads/cleanup-expired
```

Both require local-admin and Run-submitter credentials. Neither endpoint is exposed by the read-only Operations Console.

## Evidence

Canonical Events:

- `run.execution.recovered`
- `payload.retention.applied`

Event payloads contain state, reason, counters, and deadlines only. Raw request, raw claim token, encryption key, and decrypted content are never persisted.

## Non-goals

- recovery of an already `RUNNING` Product Run;
- automatic recovery at server startup;
- distributed worker leasing;
- cross-process exactly-once execution;
- local Tool approval resume;
- console mutation.
