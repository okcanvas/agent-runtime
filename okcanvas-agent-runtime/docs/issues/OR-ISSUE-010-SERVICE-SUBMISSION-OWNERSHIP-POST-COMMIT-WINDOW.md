# OR-ISSUE-010 — Service submission ownership post-commit window

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_ACCEPTANCE_PENDING`

## First affected baseline

`STEP077_PRODUCT_OWNED_BINARY_INGRESS_SLOT_LIFECYCLE` (`2.57.0`)

## Exact symptom

The service preflight route called `governed_boundary.preflight()` first. That call consumed an uploaded binary slot, created a bound encrypted record, wrote the protected payload, and committed `run_submission_preflight`. Only after that commit did the route call `ownership.register(... resource_type="submission")` and separately release the consumed slot owner.

An injected submission-ownership registration failure reproduced all of the following at once:

- HTTP 500;
- one committed `run_submission_preflight` row;
- one protected payload file;
- one bound project snapshot file;
- no submission ownership row;
- one stale ownership row for a slot file that no longer existed.

## Code-confirmed root cause

`src/okcanvas_agent_runtime/service_clients/routes.py` performed product submission persistence and service ownership projection in different transactions. Binary binding occurs inside `RunSubmissionBoundaryService.preflight()`, while service ownership was projected afterward.

The same failure cleanup also used unscoped `release_if_exists()`, which could remove a different principal's row if authorization became stale between the initial ownership check and failure cleanup.

## Impact

A transient SQLite error, injected failure, or process interruption in the post-commit window could make a real submission inaccessible through the service API while retaining encrypted payload material. It also created a stale slot owner projection. This violated the product-owned lifecycle rule that persisted resources and service ownership must transition together.

## Fix

STEP078 adds `RunSubmissionOwnershipTransition` and applies it inside the same `BEGIN IMMEDIATE` transaction that inserts or attaches a `run_submission_preflight` row:

1. insert or resolve the submission row;
2. insert or verify the `submission` owner;
3. delete matching consumed `attachment-slot` and `project-snapshot-slot` owner rows;
4. commit once.

If the transaction fails, the existing Run submission compensation deletes the newly written protected payload and bound binary records. The service route no longer performs post-commit submission registration or slot-owner release.

Failure cleanup now uses `release_if_owned()` and cannot delete another tenant/principal's ownership row.

## Automated recurrence gate

`tests/test_step078_product_owned_atomic_service_submission_ownership_transfer.py` proves:

- the old post-commit `ownership.register(submission)` path is not called;
- injected atomic-transition failure leaves no submission, payload, bound snapshot, slot file, or owner row;
- idempotent replay consumes a replacement slot and preserves exactly one submission owner;
- failure cleanup does not release another principal's owner row.

STEP078 deterministic and Windows live acceptance are additional gates.
