# Product Scope

## Product question

Can OKCanvas provide a controlled Agent runtime that uses official SDK capabilities, external Tools, and independent validators while preserving durable product state, policy, ownership, and verifiable evidence?

## Accepted proof so far

- one structured-output Agent boundary;
- Codex read-only repository inspection with Thread resume and no mutation;
- controlled Codex write in a disposable Git copy;
- exact file allowlist, external patch, unchanged source fixture and Git HEAD;
- independent pytest validation outside Codex.

## Product core

The product is not Codex. The core is:

- Task and Run lifecycle;
- immutable Agent/Tool/MCP definition references;
- ordered canonical events;
- durable approvals and execution claims;
- artifact integrity;
- independent validation;
- reference-backed implementation knowledge;
- deny-by-default Tool policy;
- operating interfaces and ownership.

## Delivery shape

Start as a Python modular monolith. Internal services are separated by contracts and repository ports, not by premature network boundaries.

## Deferred

- unrestricted external-project modification;
- dynamic Agent builder and multi-Agent organization;
- production ERP or database writes;
- broad MCP registry;
- automatic deployment;
- PlanVM execution;
- Temporal adoption;
- realtime voice;
- full Vue console;
- unrestricted shell.

These remain deferred until the relevant product-state and policy boundaries are accepted.
