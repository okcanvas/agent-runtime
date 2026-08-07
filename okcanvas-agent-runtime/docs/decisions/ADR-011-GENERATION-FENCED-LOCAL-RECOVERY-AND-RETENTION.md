# ADR-011 — Generation-fenced Local Recovery and Payload Retention

## Status

Accepted in STEP019.

## Context

STEP018 atomically created one Product Task/Run and acquired one local execution claim, but a process failure after the claim and before execution start left the submission fail-closed forever. Encrypted payloads also had no terminal or expiry lifecycle.

## Decision

1. Add a versioned governed-execution lifecycle policy.
2. Give each execution claim a short lease, owner, attempt count, and opaque generation token.
3. Persist only the token SHA-256.
4. Permit explicit recovery only for expired pre-start claims whose Task is `READY` and Run is `CREATED`.
5. Rotate the generation on recovery and fence all older scheduled work at the atomic start transition.
6. Limit claim attempts to three and record `run.execution.recovered`.
7. Delete successful payloads immediately after terminal synchronization.
8. Retain failed/cancelled payloads for seven days and unconfirmed payloads for 24 hours.
9. Perform cleanup only through an explicit bounded authenticated operation and record failures.
10. Keep active-Run recovery, startup automation, distributed workers, and console mutation disabled.

## Consequences

- A local pre-start process failure is recoverable without creating another Task/Run.
- An old scheduled generation cannot start after a new generation wins.
- This is not a distributed exactly-once guarantee.
- Failed-run evidence remains available for a bounded investigation window.
- Payload deletion failures are visible and require operator action.

## Reference decisions

- ADOPT the SDK separation of durable execution state from secrets.
- ADAPT explicit sandbox/session cleanup ownership and reconnect boundaries.
- REJECT direct `/reference` import, raw claim-token persistence, active-Run reclaim, and silent deletion failure.
