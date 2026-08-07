# STEP078 Product-owned atomic service submission ownership transfer

```text
step: STEP078_PRODUCT_OWNED_ATOMIC_SERVICE_SUBMISSION_OWNERSHIP_TRANSFER
version: 2.58.0
state: IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING
```

## Goal

Remove the service API failure window between a committed governed submission and its tenant/principal ownership projection.

## Selected source defect

STEP077 service preflight committed the submission, protected payload, and bound binary input before it separately registered the `submission` owner and released the consumed slot owner. An injected ownership failure reproduced inaccessible retained resources and a stale slot owner.

## Product path

```text
authenticated principal owns ingress slot
→ inspect and bind encrypted input
→ write protected payload
→ BEGIN IMMEDIATE on product SQLite
→ insert/resolve run_submission_preflight
→ insert/verify submission owner
→ delete same-principal consumed slot owner rows
→ COMMIT
```

The transaction permits a consumed owner row to be absent after a previously authorized concurrent cleanup, but rejects an existing row owned by another principal. Service failure cleanup is principal-scoped.

## Files

- `run_submission/models.py`: `RunSubmissionOwnershipTransition` contract.
- `run_submission/store.py`: atomic ownership transition during register, replay, and payload attachment.
- `run_submission/service.py`: transition propagation and existing-idempotency handling.
- `service_clients/routes.py`: construct transition and remove post-commit ownership calls.
- `service_clients/ownership.py`: principal-scoped idempotent release.
- `tests/test_step078_product_owned_atomic_service_submission_ownership_transfer.py`: recurrence gates.

## Non-goals

- session creation ownership atomicity;
- Task/Run/Approval ownership projection atomicity;
- distributed transactions or external object storage;
- changes to Sandbox, model, Tool, encryption, ZIP, or attachment content policy.

## Packaging validation correction

OR-ISSUE-011 bounds the no-direct-reference-import verifier by extracting call source only from files containing `reference/upstream`; its import checks and forbidden dynamic-load checks are unchanged.
