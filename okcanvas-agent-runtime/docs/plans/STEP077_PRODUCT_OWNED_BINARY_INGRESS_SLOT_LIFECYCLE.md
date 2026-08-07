# STEP077 — Product-owned binary ingress slot lifecycle

## Identity

```text
step: STEP077_PRODUCT_OWNED_BINARY_INGRESS_SLOT_LIFECYCLE
version: 2.57.0
predecessor: STEP076_PRODUCT_OWNED_IMMUTABLE_PROJECT_SNAPSHOT_BINDING
```

## Predecessor closure

STEP076 deterministic acceptance passed 37/37. The user’s Windows live run passed 46/46 with `gpt-4.1`, model calls 2, Tool calls 1, terminal status `SUCCEEDED`, selected-file hashes verified, cleanup `COMPLETED`, orphan count 0 and no raw archive/workspace/API-key persistence.

## Problem selected from source audit

The STEP076 implementation could split encrypted filesystem state from the SQLite ownership projection during upload failure and expiry. Project-snapshot creation also omitted the cleanup call used by the attachment store, and neither resource exposed an authenticated user delete route.

## Product contract

### Authenticated expiry reconciliation

- Scan only the fixed `slots` directory and fixed slot-ID filename patterns.
- Reject symbolic-link slot files.
- Authenticate/decrypt each candidate envelope before trusting its metadata or expiry.
- Delete only authenticated slots whose `expires_at` is not later than current UTC.
- Return exact opaque slot refs deleted by the store.
- The service deletes matching ownership rows with an idempotent internal release operation.
- Run reconciliation before both upload APIs and before governed preflight.

### Ownership registration compensation

- Create and validate the encrypted slot first.
- Register principal ownership second.
- If registration fails, delete the just-created encrypted slot and propagate the failure.
- Do not return a slot ID unless both file creation and ownership registration succeed.

### Explicit deletion

```text
DELETE /v1/service/local-attachments/{attachment_id}
DELETE /v1/service/project-snapshots/{project_snapshot_id}
```

- Require the `agent-user` role and exact principal ownership.
- Preserve 404 for cross-scope access.
- Delete the encrypted file and then release ownership.
- Return 204 with no body.

### Preflight failure reconciliation

If preflight fails after a slot has been consumed or invalidated, release its ownership row only when the physical slot no longer exists. Do not delete valid still-existing slots on unrelated validation failures.

## Unchanged boundaries

- AES-256-GCM storage and dedicated subkeys are unchanged.
- Project ZIP validation and attachment MIME/size validation are unchanged.
- Submission fingerprint and immutable bound snapshot behavior are unchanged.
- Sandbox remains network none, Shell disabled, Apply Patch disabled and one fixed read-only Tool.
- Raw upload bytes, source, host paths, API keys and bearer tokens remain excluded from Events and Artifacts.

## Acceptance

Deterministic acceptance must prove all lifecycle contracts without Docker, external network or model calls. Windows live acceptance must use the real LLM/Sandbox path and additionally prove:

- snapshot DELETE returns 204 and removes file/owner;
- attachment DELETE returns 204 and removes file/owner;
- an authenticated expired snapshot is removed with its ownership row before a new upload;
- the accepted STEP076 immutable snapshot execution still succeeds with model calls 2 and Tool calls 1;
- final check count is 50: 49 workflow checks plus `api_key_not_in_summary`.
