# ADR-008: Product State Is Not SDK State

## Status
Accepted.

## Decision
Task, Run, Approval, canonical Event, Artifact, and Validation records are owned by the OKCanvas product store. Agents SDK Session, RunState, stream events, traces, and Codex Thread IDs are adapter state referenced by product records.

## Rationale
The inspected Session protocol stores conversation items. RunState resumes one Agent execution. Traces provide diagnostics. None defines user ownership, work lifecycle, artifact integrity, approval ledger, or independent validation.

## Consequence
SDK upgrades can change adapter serialization and events without changing the public product contract. Migration metadata and hashes are required for any persisted SDK state.
