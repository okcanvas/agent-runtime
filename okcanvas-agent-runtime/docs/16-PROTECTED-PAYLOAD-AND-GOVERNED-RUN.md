# Protected Payload and Governed Read-only Run

## Purpose

STEP018 converts a confirmed read-only submission into exactly one Product Task/Run without putting the raw request into SQLite, canonical Events, or the submission ledger.

## Authority boundary

Two separate credentials are required:

- `X-OKCanvas-Admin-Key`: local administrative read/control authentication;
- `X-OKCanvas-Run-Submitter-Key`: explicit model-execution submission authority.

The keys must be distinct. A server without the Run-submitter key and payload-key configuration remains usable for read-only operations but returns a canonical `503 RUN_SUBMISSION_NOT_CONFIGURED` for governed mutation endpoints.

## Protected payload

Backend:

```text
AES-256-GCM
12-byte random nonce
canonical JSON plaintext
canonical JSON authenticated additional data
atomic file write
opaque payload reference
```

The encrypted envelope contains metadata needed for decryption and integrity validation, but not the raw request in plaintext. The key remains in process memory from `OKCANVAS_PROTECTED_PAYLOAD_KEY` and is represented in storage only by a non-secret SHA-256-derived `key_id` prefix.

SQLite stores:

- opaque `protected_payload_ref`;
- encrypted file SHA-256;
- encrypted file byte length;
- key fingerprint;
- input SHA-256 and request fingerprint.

SQLite does not store:

- raw request;
- raw idempotency key;
- encryption key;
- nonce/ciphertext body;
- Tool arguments/results;
- model output.

## Preflight

`POST /v1/run-submissions/preflight`:

1. validates separate authority;
2. resolves immutable Agent and MCP definitions;
3. classifies capability mode;
4. binds model, definition SHA, policy SHA, input SHA, and execution mode into one request fingerprint;
5. enforces idempotency;
6. encrypts the request only for `IMMEDIATE_AFTER_CONFIRMATION` read-only Agents;
7. stores the submission ledger record;
8. creates no Product Task or Run and invokes no model.

Local Tool and proposal-only submissions do not receive a protected payload in STEP018 because they are not executable through this path.

## Confirmation and execution

`POST /v1/run-submissions/{submission_id}/confirm`:

1. requires the exact challenge;
2. rechecks policy SHA and selected model;
3. verifies encrypted file path, byte length, SHA, key ID, AES-GCM tag, and authenticated metadata;
4. verifies decrypted identity against the ledger;
5. resolves the current immutable Agent definition and rejects drift;
6. creates Task, Run, `run.created`, and submission binding in one SQLite transaction;
7. claims execution through a compare-and-set state transition;
8. schedules the existing generic execution service only for the winning claim.

Repeated confirmation returns the already-bound Task/Run and does not create or schedule another execution.

## Submission states

```text
READY_FOR_CONFIRMATION
→ RUN_CREATED
→ EXECUTION_CLAIMED
→ EXECUTION_SCHEDULED
```

Other modes remain:

```text
APPROVAL_PATH_REQUIRED
PROPOSAL_ONLY
```

## Failure behavior

- wrong confirmation: no Task/Run;
- changed policy, model, Agent SHA, or payload metadata: fail closed;
- missing, moved, symlinked, truncated, changed, or wrongly keyed payload: fail closed;
- concurrent confirmation: one Task/Run and one execution claim;
- failure after the execution claim: state remains for investigation; automatic recovery is not claimed.

## Retention boundary

STEP018 does not automatically delete protected payloads. Deleting immediately after scheduling would weaken restart/recovery and failure investigation before those contracts exist. STEP019 must define terminal retention, failure preservation, operator cleanup, and claim recovery together.

## Non-scope

- local Tool approval execution;
- write MCP;
- Handoff or Session execution;
- Codex write through governed submission;
- console submission UI;
- distributed workers;
- durable multi-process lease;
- automatic active-Run recovery.

## STEP019 lifecycle extension

Claim recovery and payload retention are now governed by `specs/submissions/governed-execution-lifecycle-policy.json`. See `docs/17-GOVERNED-RECOVERY-AND-PAYLOAD-RETENTION.md`. Successful payloads are deleted immediately; failed/cancelled and unconfirmed payloads follow bounded retention. Only stale pre-start claims may be explicitly recovered, with generation fencing.

## STEP046 Session identity binding

Protected payload content schema `okcanvas-protected-payload-content-v3` adds nullable `session_id` to both authenticated AAD and encrypted content. A Session-bound submission must decrypt to the exact Session ID in the immutable submission ledger. A missing, added or changed Session ID fails before Tool approval prepare/resume or normal execution.

The schema change does not place Session history in protected payload storage. It stores only the existing governed request plus immutable Session identity.
