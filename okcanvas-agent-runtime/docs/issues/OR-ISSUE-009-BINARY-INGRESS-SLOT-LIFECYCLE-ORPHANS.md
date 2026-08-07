# OR-ISSUE-009 — Binary ingress slot files and ownership rows could become orphaned

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Exact code-confirmed symptom

The STEP076 source established encrypted upload slots for project snapshots and local attachments, but the file store and service ownership projection did not form one complete lifecycle.

- `EncryptedProjectSnapshotStore.create_slot()` initialized storage and wrote a new slot without first invoking expired-slot cleanup.
- The snapshot and attachment upload routes created the encrypted file before calling `ServiceResourceOwnershipStore.register()`.
- If ownership registration raised, the route propagated the exception and left the encrypted slot file behind.
- Store-level expiry cleanup deleted files only. It had no access to the SQLite ownership projection, so an expired file could leave a stale `project-snapshot-slot` or `attachment-slot` ownership row.
- No authenticated DELETE route existed for a principal to abandon an unused slot before TTL expiry.

These facts were confirmed directly in the STEP076 packaged source. No claim is made that the accepted STEP076 Windows run leaked a slot; the defect was an unclosed error/expiry lifecycle in long-running service operation.

## Impact

- encrypted files could accumulate after ownership-database failures;
- stale ownership rows could survive expired file deletion;
- an abandoned upload could only wait for TTL cleanup;
- file existence and ownership projection could disagree;
- storage/ledger orphan counts were not bounded by a service-level reconciliation path.

## Root cause

Binary ingress was implemented as two durable components with separate transactions:

1. encrypted filesystem slot;
2. SQLite principal-ownership projection.

STEP076 correctly protected bytes and access scope, but did not add compensating actions and reconciliation across those components.

## Fix

STEP077 implements Product-owned lifecycle closure:

1. Both encrypted stores expose bounded `slot_exists()`, boolean `delete()` and authenticated `cleanup_expired_slot_refs()` operations.
2. A new upload invokes expiry cleanup before writing another slot.
3. Expiry scanning authenticates each AES-GCM envelope through `_read_record(..., expected_type="slot")`; filenames alone never authorize deletion.
4. The service router reconciles every returned expired slot reference with `release_if_exists()` in the ownership store.
5. Reconciliation runs before attachment upload, project-snapshot upload and governed submission preflight.
6. If ownership registration fails after encrypted-file creation, the route immediately deletes that file and re-raises the original failure.
7. Owner-scoped DELETE routes remove the encrypted file and ownership row. `require_principal()` preserves cross-tenant/cross-principal 404 behavior.
8. If preflight consumes or deletes a slot and then fails, the service checks physical existence and releases only ownership rows whose slot no longer exists.

## Persisted-data boundary

The lifecycle operations do not persist raw upload bytes, raw archive, host path, filename lists, bearer tokens or API keys. They operate on opaque slot IDs and existing encrypted envelopes.

## Recurrence gates

`tests/test_step077_product_owned_binary_ingress_slot_lifecycle.py` proves:

- expired project snapshot file and ownership row are removed before a replacement upload;
- explicit delete removes both file and owner row for snapshot and attachment slots;
- cross-principal delete remains 404 and does not delete the owner’s slot;
- injected ownership-registration failure leaves no encrypted file;
- preflight reconciliation removes expired file and ownership row.

STEP077 deterministic acceptance also checks source contracts, service policy, runtime flags, focused/historical regression, Node release/tests, Reference integrity, packaging exclusions and zero Docker/model/network activity.
