# STEP034 — Orphaned RUNNING Run Reconciliation

STEP034 strengthens the reusable Agent Runtime after STEP033 bound the executable Runtime to confirmation. It addresses a separate process-loss gap: a governed submission that had already entered `EXECUTION_STARTED` left its Product Task and Run permanently `RUNNING` when the hosting process disappeared.

## Code-audited defect

Before STEP034, stale recovery covered only `EXECUTION_CLAIMED` and `EXECUTION_SCHEDULED` while Product state remained `READY/CREATED`. Once `begin_execution()` atomically changed the submission to `EXECUTION_STARTED` and Product state to `RUNNING`, `claim_expires_at` was cleared and no recovery or terminal reconciliation path included that state.

A new process could therefore read the durable state but could neither prove success nor close the orphan. Re-running the model was rejected because the prior external call might already have executed.

## Implemented boundary

The authenticated explicit operator endpoint is:

```text
POST /v1/run-submissions/reconcile-orphaned-running
confirmation=RECONCILE_ORPHANED_RUNNING_AFTER_PROCESS_RESTART
```

A candidate must satisfy all of the following:

- submission state is `EXECUTION_STARTED`;
- Product Task and Run are both `RUNNING`;
- the persisted claim owner differs from the current local process owner;
- no Artifact has been registered for the Run.

The reconciliation transaction:

1. sets the same Task and Run to `FAILED`;
2. emits `run.execution.orphaned`;
3. emits terminal `run.failed` with `PROCESS_LOSS_RECONCILED`, `retryable=false`;
4. emits `payload.retention.applied`;
5. sets the submission to `EXECUTION_FAILED`;
6. clears the old claim generation;
7. retains the protected payload for the existing seven-day failure investigation window.

It creates no new Task or Run and never calls the model, MCP, or Tool gateway.

## Late previous-process fencing

A previous process can theoretically return after the new process reconciles the Run. STEP034 therefore keeps the claim token as a generation fence throughout governed execution.

The generic execution path checks the fence before lifecycle Event persistence, after the model call, and around Artifact creation. Product-store mutations also fail closed when a Run is already terminal:

- active execution Events cannot be appended to a terminal Run;
- execution metadata cannot be updated on a terminal Run;
- an Artifact cannot be registered for a terminal Run.

If Artifact registration won the SQLite transaction race first, the orphan query excludes that Run and does not falsely terminalize it.

## Reference decision

The retained SDK `RunState` implementation is a durable interruption/resume boundary, especially for human-in-the-loop flows. It is not evidence that an arbitrary in-flight model request can be resumed after process death. STEP034 therefore rejects SDK resume and model re-execution for this state.

Inspected:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_state.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/result.py`

No Reference code is imported or executed.

## Explicit non-scope

STEP034 does not add:

- automatic startup reconciliation;
- SDK Session or arbitrary in-flight model resume;
- model retry or replacement Run creation;
- distributed worker leasing;
- cancellation of an already transmitted external model request;
- cross-process exactly-once execution claims.

It provides one safe Product outcome after an explicitly confirmed local process restart: fail the orphan, fence late writes, and retain investigation material.
