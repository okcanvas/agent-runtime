# ADR-010 — Protected Payload and Atomic Run Binding

## Status

Accepted in STEP018.

## Context

STEP017 proved authority separation, fingerprint confirmation, and idempotent preflight but deliberately persisted no raw input and created no Product Task/Run. Actual governed execution needs the request after confirmation without weakening the product-state or secret-persistence boundaries.

The inspected SDK RunState is the durable pause/resume representation for SDK execution. Its guidance explicitly warns against persisting secrets in context, traces, or Tool output. It is not the Product request vault or Task/Run ledger.

## Decision

1. Store the raw request in a product-owned AES-256-GCM encrypted file outside SQLite.
2. Keep the encryption key only in environment/process memory.
3. Bind the encrypted file to submission identity and immutable execution metadata through authenticated additional data.
4. Store only an opaque reference, encrypted-file integrity metadata, and non-secret key fingerprint in SQLite.
5. Create Product Task, Run, initial Event, and submission binding in one SQLite transaction after exact confirmation and integrity revalidation.
6. Use a compare-and-set execution claim so repeated/concurrent confirmations schedule at most one execution in the current process.
7. Keep local Tool and mutation-capable paths disabled.

## Consequences

- Raw input is recoverable for confirmed execution without entering the product ledger.
- Payload tampering, wrong key, definition drift, and policy drift fail closed.
- The Product Task/Run is exactly-once within the SQLite binding transaction.
- Execution scheduling is not a distributed exactly-once guarantee.
- Payload retention and stale execution-claim recovery must be designed together in a later STEP.

## Reference decisions

- ADOPT the SDK distinction between durable RunState and external secrets.
- ADAPT owner-only sensitive file creation patterns from sandbox mount helpers.
- ADAPT API-key hashing/non-persistence principles from tracing code.
- REJECT direct `/reference` import and SDK RunState as a secret store.
