# STEP024 — Store replenishment review Agent vertical slice

## Goal

Prove that the governed runtime can support one useful commerce-shaped Agent without expanding approval infrastructure or adding external integration complexity.

## Scope

- add one immutable read-only Agent definition;
- add one business-specific structured output contract;
- enforce replenishment equations and aggregate consistency in runtime validation;
- add one canonical shortage case pack;
- execute through the existing protected governed read-only submission path;
- store a verified Artifact and evaluate the recorded Run deterministically;
- provide deterministic and optional installed-SDK Windows acceptance commands.

## Non-scope

- external ERP/store MCP;
- inventory mutation;
- purchase-order generation;
- additional Agents, Tools, Handoffs, or Sessions;
- approval UI or batch operation;
- distributed workers.

## Acceptance

- preflight creates no Task or Run;
- exact confirmation creates exactly one Task and Run;
- result satisfies the business output contract;
- case001 yields reorder quantities 12, 7, and 0, total 19;
- no Tool or MCP events occur;
- output Artifact verifies;
- recorded-Run evaluation passes;
- raw input and keys are absent from Product SQLite;
- successful protected payload is deleted;
- references remain unchanged;
- Acceptance Workspace cleanup completes.
