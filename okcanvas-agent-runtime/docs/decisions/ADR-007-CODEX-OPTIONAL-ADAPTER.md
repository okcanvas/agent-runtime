# ADR-007: Codex Is an Optional Integration Adapter

## Status
Accepted.

## Decision
Codex is not the central runtime architecture. It is an optional specialized Tool adapter under `integrations/codex` conceptually, protected by feature flags, policy, acceptance tests, and independent validation.

## Evidence
The inspected Codex integration is under `agents.extensions.experimental`. STEP002 and STEP003 proved useful read and controlled-write slices, but their costs, CLI dependency, workspace policy, and experimental API are specific to coding work.

## Consequence
Core Task, Run, Event, Approval, Artifact, Reference, Validation, API, and MCP work may continue without completing every Codex-specific step. Codex state is linked to a Run but does not define the Run model.
