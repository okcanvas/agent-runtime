# STEP079 code audit — Atomic Task/Run ownership transfer

## Audited STEP078 source

The following packaged source was inspected before modification:

- `service_clients/routes.py` confirmation route;
- `run_submission/execution.py` scheduling and replay path;
- `run_submission/store.py` Task/Run transaction;
- `service_clients/ownership.py` separate ownership projection.

## Reproduction

The canonical STEP078 app was started with its Product SQLite database and no-op test model gateway. A valid immutable project snapshot and governed submission were created. `service_resource_ownership.register()` was injected to fail for `task`, then the exact confirmation endpoint was called.

Observed:

```text
HTTP: 500
submission state: EXECUTION_FAILED
Task rows: 1
Run rows: 1
Task owner rows: 0
Run owner rows: 0
submission owner rows: 1
```

This confirms a real post-commit ownership window rather than a speculative design concern.

## Implemented code path

`RunExecutionOwnershipTransition` carries only validated tenant/principal identity. `SQLiteRunSubmissionStore.create_governed_task_run()` now:

1. opens `BEGIN IMMEDIATE`;
2. resolves or creates exactly one Task and Run;
3. writes the submission Task/Run binding and `run.created` event;
4. inserts or verifies `task` and `run` owner rows;
5. commits once.

For existing Task/Run bindings, the same transaction verifies or restores owner rows before returning replay. Foreign ownership raises `RunSubmissionIntegrityError` and rolls back.

`GovernedReadOnlyRunSubmissionService` propagates the transition through new confirmation and terminal replay paths. Recovery remains an internal Product path and does not invent service ownership. `service_clients/routes.py` supplies the authenticated principal and has no post-commit Task/Run registration.

## Preserved boundaries

- STEP078 atomic submission/ingress ownership remains active and Windows accepted.
- Immutable project snapshot and protected payload identity remain unchanged.
- Exactly two model calls and one read-only Sandbox Tool call remain the live bound.
- Docker network remains `none`; Shell and Apply Patch remain disabled.
- Raw source, raw archive, model draft, Tool raw result, bearer token and API key are not persisted.
- Product-owned immutable Skill `document-review-v1` remains installed and unchanged.
