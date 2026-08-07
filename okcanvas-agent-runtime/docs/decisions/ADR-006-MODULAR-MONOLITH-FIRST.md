# ADR-006: Modular Monolith First

## Status
Accepted.

## Decision
Build the Agent platform as one Python package with explicit internal service and repository ports. Do not create network microservices for Task, Run, Approval, Reference, Artifact, or Validation during the initial phases.

## Evidence
The supplied SDK already introduces asynchronous model, Tool, MCP, Session, tracing, and sandbox boundaries. Premature network boundaries would add failure and deployment modes before the product state model is stable.

## Consequence
Separate processes may exist for safety, such as the independent Validator or future worker, while code and contracts remain in one repository. A module is split into a network service only after independent scaling, privilege, or availability evidence exists.
