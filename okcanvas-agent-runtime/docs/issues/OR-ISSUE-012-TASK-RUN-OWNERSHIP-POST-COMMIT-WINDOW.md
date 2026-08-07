# OR-ISSUE-012 — Product Task/Run ownership post-commit window

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Exact symptom

STEP078 service confirmation called `GovernedReadOnlyRunSubmissionService.confirm_and_schedule()`, which committed the Product Task, Product Run, submission binding, execution claim and schedule before `service_clients/routes.py` separately called:

```text
ownership.register(task)
ownership.register(run)
```

The packaged STEP078 code was executed with `service_resource_ownership.register()` forced to fail for `task`. The HTTP request returned 500. The database retained one bound Task and Run in terminal `FAILED` state, while `service_resource_owner` contained only the submission owner. The real Task/Run therefore existed but could not be read through the owner-scoped service API.

## Code-confirmed root cause

`SQLiteRunSubmissionStore.create_governed_task_run()` already created Task, Run, `run.created`, and the submission Task/Run binding in one `BEGIN IMMEDIATE` transaction. Service ownership was not part of that transaction. The route projected ownership only after `confirm_and_schedule()` returned.

## Impact

A transient SQLite ownership error or process interruption could create an inaccessible Product Task/Run. A retry could not reliably distinguish an unowned legitimate execution from a foreign-owned resource. The service ownership contract was therefore weaker than the Product persistence contract.

## Fix

STEP079 adds immutable `RunExecutionOwnershipTransition`. `create_governed_task_run()` now creates or verifies exact `task` and `run` owner rows using the same SQLite connection and transaction that creates or resolves the Product Task/Run binding. Existing/replayed Task/Run IDs are also verified or repaired transactionally. A conflicting tenant/principal owner fails closed without replacing that owner.

The service route passes the authenticated tenant/principal into `confirm_and_schedule()` and no longer calls post-commit `ownership.register(task/run)`.

## Evidence

`tests/test_step079_product_owned_atomic_task_run_ownership_transfer.py` proves:

- the removed post-commit register path is not called;
- Task, Run and both owner rows are committed together;
- injected ownership transition failure rolls back Task, Run and the submission binding;
- replay repairs missing same-principal owner rows;
- foreign Task/Run owners cause conflict and are not stolen.

STEP079 deterministic and Windows live acceptance preserve this gate.
