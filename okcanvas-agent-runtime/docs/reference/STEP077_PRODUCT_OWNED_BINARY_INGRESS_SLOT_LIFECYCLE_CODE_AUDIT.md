# STEP077 code audit — binary ingress slot lifecycle

## Audit rule

No behavior was inferred from naming or documents. The STEP076 ZIP was unpacked and the active stores, service routes, ownership projection, runtime flags, tests, launchers and packaging code were inspected directly.

## STEP076 gaps confirmed in source

### Project snapshot expiry

`src/okcanvas_agent_runtime/project_snapshots/store.py` created a new slot after `initialize()` but did not call cleanup. Therefore project snapshot expiry depended on another explicit caller that did not exist in the service upload path.

### Split file/ownership transaction

`src/okcanvas_agent_runtime/service_clients/routes.py` created encrypted snapshot/attachment files before calling ownership registration. The exception path had no compensating file deletion.

### Stale ownership projection

Store cleanup could delete expired files but returned only a count and could not remove rows from `service_resource_ownership`. The service layer had no reconciliation operation joining those results.

### No user abandonment operation

The router exposed POST ingress APIs but no DELETE routes for unused slots.

## Implemented source path

### Stores

`project_snapshots/store.py` and `attachments/store.py` now:

- reconcile expired slots before new slot creation;
- return exact deleted refs from `cleanup_expired_slot_refs()`;
- authenticate each candidate envelope before expiry evaluation;
- expose `slot_exists()` and boolean `delete()`.

### Ownership projection

`service_clients/ownership.py` adds `release_if_exists()` for internal idempotent reconciliation while retaining principal validation in the public `release()` path.

### Service router

`service_clients/routes.py` now:

- reconciles expired snapshot/attachment refs and ownership rows before upload/preflight;
- compensates file creation if ownership registration fails;
- exposes principal-scoped 204 DELETE routes;
- releases missing ownership after a failed preflight only when the physical slot is gone;
- advertises `binary-ingress-slot-delete` and `binary-ingress-expiry-reconciliation` capabilities.

### Runtime and policy

- baseline version is `2.57.0` / STEP077;
- STEP076 Windows live flag is closed `true`;
- STEP077 deterministic flag is `true`, Windows live flag remains `false`;
- service policy version is `1.6.0` and selects STEP077.

## Security invariants preserved

- cross-scope disclosure remains HTTP 404;
- expiry scanning does not trust unauthenticated filenames or plaintext metadata;
- no wildcard host deletion is used;
- raw content and secrets are not added to lifecycle evidence;
- snapshot/archive hashes and per-submission binding are unchanged;
- Sandbox network/Shell/Apply Patch boundaries are unchanged.

## Tests

The new STEP077 test module injects ownership registration failures, creates cryptographically valid expired envelopes, exercises service DELETE routes, verifies cross-principal isolation and checks both encrypted files and SQLite rows. Existing STEP076, STEP069, STEP068, submission, gateway and Windows-entrypoint tests are included in focused acceptance.
