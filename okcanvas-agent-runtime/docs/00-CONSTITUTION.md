# Constitution

The binding constitution is `AGENTS.md`. This document explains the product-level consequences.

- The runtime may reason and propose, but claims must be backed by code or execution evidence.
- External reference repositories are immutable study material and must be actively consulted as implementation answer keys.
- Relevant work must inspect applicable reference code before inventing or reimplementing SDK, state, MCP, tracing, streaming, Codex, workflow, or UI mechanisms.
- Each material design decision records what reference behavior was adopted, adapted, deferred, or rejected.
- Tool permissions are explicit, narrow, and deny-by-default.
- Agent conversation state, durable task state, workspace state, and evidence are separate concepts.
- PlanVM remains a deterministic plan runner, not the central planner, skill registry, or agent runtime.
- Codex is treated as a specialized coding tool rather than reimplemented from generic shell primitives.


## Acceptance workspace lifecycle

Deterministic acceptance state is isolated from Product runtime state. Resources must close explicitly before cleanup. PASS exports compact Evidence and removes the workspace. FAIL, exception, close failure, or cleanup failure preserves the exact workspace path. Cleanup retries are bounded and never substitute for resource closure.

## Run-submission authority

Read-only operations access never implies authority to spend model tokens or invoke Tools. A governed Run submission requires a separate submit authority, immutable Agent capability classification, mandatory idempotency, and exact confirmation bound to the request fingerprint. Raw input and raw idempotency keys must not be stored in the submission ledger. Mutation-capable paths require persisted SDK approval or remain proposal-only.

## Approval operator boundary

Approval observation and approval decisions remain separate. The general Operations Console is read-only. A local decision requires both local-admin and Run-submitter authority and an exact confirmation bound to the approval ID, Run ID, and decision. Credential-bearing operator traffic is loopback-only. Batch and always-approve behavior remain disabled.

