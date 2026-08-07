# STEP034_ORPHANED_RUNNING_RUN_RECONCILIATION

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Goal

Close previous-process governed `EXECUTION_STARTED/RUNNING` state without re-running the model and without permitting late old-generation writes.

## Scope

- explicit authenticated local-operator reconciliation;
- candidate selection by different process owner, exact Product state, and absence of Artifact;
- atomic Task/Run/submission failure;
- canonical orphan/failure/retention Events;
- old claim generation invalidation;
- active execution Event, metadata, and Artifact terminal-state fencing;
- failed protected-payload retention;
- deterministic and Windows acceptance.

## Rejected

- automatic startup mutation;
- SDK resume of an arbitrary in-flight model call;
- replacement Task/Run or automatic model retry;
- distributed lease claims;
- domain-specific behavior.

## Acceptance

Run `sh_run_step034_acceptance.cmd` and require:

- `state=PASSED` and all 20 checks true;
- one orphan scanned and reconciled;
- exact `PROCESS_LOSS_RECONCILED`, `retryable=false` failure;
- previous generation active before and inactive after reconciliation;
- late Event, metadata, and Artifact writes blocked;
- gateway calls 0;
- Artifacts and Evaluations 0;
- one retained protected payload;
- replay scans and reconciles 0;
- cleanup `COMPLETED`.
