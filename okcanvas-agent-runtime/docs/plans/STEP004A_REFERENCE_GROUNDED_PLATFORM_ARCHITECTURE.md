# STEP004A_REFERENCE_GROUNDED_PLATFORM_ARCHITECTURE

## Objective

Rebase the delivery plan on the full supplied reference source and prevent Codex-specific implementation from becoming the product architecture.

## Current code evidence

- STEP002 read-only Codex and STEP003 disposable write are live accepted.
- STEP004 persisted approval is implemented but not live accepted.
- The primary SDK contains Runner, RunState, Session, streaming, tracing, MCP, sandbox, and experimental Codex implementations.
- The supplied demos illustrate useful UX, streaming, and durable-workflow patterns but do not provide production product state or authorization.

## Scope

- reference adoption matrix;
- product versus SDK state boundary;
- internal service boundaries;
- modular-monolith decision;
- Codex optional-adapter decision;
- primary and parallel delivery tracks;
- STEP005 exact next scope.

## Non-scope

- no new runtime feature;
- no source package reorganization;
- no database implementation;
- no REST/SSE, MCP, PlanVM, Temporal, UI, or external project integration;
- no STEP004 live execution.

## Acceptance criteria

- architecture documents cite inspected reference paths;
- Codex is not a prerequisite for STEP005;
- Task/Run/Event/Approval/Artifact/Validation ownership is explicit;
- Session, RunState, Trace, and Codex Thread roles are separated;
- roadmap has bounded acceptance criteria for STEP005–STEP010;
- regression tests and reference integrity remain green.
