# ADR-009: Local Run Submission Authority and Approval

## Status

Accepted for STEP017.

## Decision

Local operations read authority and Run-submission authority are separate capabilities. The read-only console continues to use `X-OKCanvas-Admin-Key`, but a future submission action must prove `LOCAL_RUN_SUBMITTER` authority, an idempotency key, and the exact fingerprint confirmation challenge.

Execution mode is derived from immutable Agent and MCP definitions:

- no local Tools, no Handoffs, disabled Session, and read-only MCP only: `IMMEDIATE_AFTER_CONFIRMATION`;
- local Tool present: `APPROVAL_INTERRUPTED` using the installed Agents SDK `RunState` approval boundary;
- write MCP, Handoff, or Session orchestration: `PROPOSAL_ONLY` until a separate constitution enables it.

STEP017 persists only a preflight ledger. It does not persist raw input, schedule a model call, create a Task/Run, or add a console mutation.

The legacy direct `POST /v1/runs` route is disabled by default and may be enabled only for controlled compatibility or acceptance runs.

## Rationale

Authentication alone is not authorization to spend model tokens or invoke Tools. A boolean confirmation is also too weak because it is not bound to Agent identity, input, model, and immutable policy. Idempotency must survive retries without storing the raw key or raw request.

## Consequences

- a future submit endpoint must reuse the STEP017 fingerprint and idempotency contracts;
- a protected payload service is required before approval-interrupted submissions can survive process restart;
- the console remains read-only in STEP017;
- Codex write, write MCP, deployment, and broad mutation controls remain outside this boundary.
