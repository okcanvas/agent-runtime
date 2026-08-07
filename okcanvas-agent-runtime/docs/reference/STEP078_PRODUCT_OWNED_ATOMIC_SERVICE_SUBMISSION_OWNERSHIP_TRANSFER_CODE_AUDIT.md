# STEP078 code audit

## Audited STEP077 path

`service_clients/routes.py::preflight` performed:

```text
governed_boundary.preflight(...)
ownership.register(submission)
ownership.release(ingress slot)
```

`RunSubmissionBoundaryService.preflight` had already bound/deleted the slot, written the protected payload, and committed the submission before returning.

## Reproduction

With only `ownership.register(resource_type="submission")` forced to raise, the STEP077 ZIP produced HTTP 500 while retaining:

```text
run_submission_preflight rows: 1
protected payload files: 1
bound snapshot files: 1
submission owner rows: 0
stale consumed-slot owner rows: 1
```

This was executed against the unpacked canonical STEP077 source before modification.

## Implemented transaction

`SQLiteRunSubmissionStore` now accepts `RunSubmissionOwnershipTransition` in:

- `register()`;
- `attach_payload()`;
- `apply_ownership_transition()` for idempotent replay.

The private `_apply_ownership_transition()` runs on the caller's existing SQLite connection and transaction. It verifies an existing submission owner, inserts it if absent, rejects foreign ownership, and removes same-principal consumed ingress owner rows.

## Compensation

If `_apply_ownership_transition()` raises during a new preflight, the SQLite INSERT rolls back. Existing boundary compensation deletes the protected payload and bound snapshot/attachment. The route then removes only the current principal's missing-slot projection through `release_if_owned()`.

## Preserved boundaries

- AES-256-GCM payload, attachment, and snapshot stores unchanged;
- immutable snapshot hashes and submission fingerprint unchanged;
- no raw source/archive/API key persistence;
- Docker network none, Shell disabled, Apply Patch disabled;
- exactly one fixed read-only Sandbox Tool remains.

## Acceptance verifier audit

Integrated acceptance exposed OR-ISSUE-011: every `ast.Call` previously invoked source-segment extraction even when `reference/upstream` was absent. The new source-token guard preserves the same forbidden cases and is covered by a failing-sentinel regression test.
