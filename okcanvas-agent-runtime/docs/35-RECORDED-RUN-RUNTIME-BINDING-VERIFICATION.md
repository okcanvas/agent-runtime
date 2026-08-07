# STEP036 — Recorded Run Runtime Binding Verification

STEP033 bound executable Agent Runtime behavior at preflight and confirmation time. Before STEP036, the recorded-Run Evaluation path verified the Agent definition, terminal Product state, canonical Events, final-output Artifact, and output contract, but it did not re-resolve and verify the recorded `runtime_binding_sha256`.

## Defect

A completed Run could carry one Runtime binding in `agent.definition.resolved`, while Evaluation after a package or policy change validated only the Agent definition and Artifact. Output-contract Runtime, SDK version, MCP module, local Tool policy, and execution-engine drift could therefore be omitted from the Evaluation trust decision.

## Implemented boundary

`RecordedRunEvaluationService` now:

1. resolves the immutable Agent definition;
2. resolves the current product-owned `AgentRuntimeBinding` for that definition;
3. requires exactly one recorded `runtime_binding_sha256` in `agent.definition.resolved`;
4. requires the recorded SHA to equal the current executable Runtime binding;
5. verifies the Event's output contract, MCP server list/count, local Tool count, handoff count, and session mode against the definition;
6. persists `subject_runtime_binding_sha256` with the Evaluation result;
7. exposes that SHA through the local-admin Evaluation API;
8. fails closed with HTTP 409 / `RUNTIME_BINDING_DRIFT` and creates no Evaluation when the recorded binding or current Runtime differs.

## Legacy behavior

Runs recorded before STEP033 may not contain a provable Runtime binding. STEP036 does not infer or backfill one. Such Runs fail closed and must not be treated as comparable Evaluation evidence.

Existing Evaluation SQLite databases are migrated additively with a non-secret `subject_runtime_binding_sha256` column. Existing historical Evaluation rows retain an empty value because their binding was not recorded by the older schema.

## Non-goals

STEP036 does not:

- execute or resume an Agent during Evaluation;
- call a model, MCP server, or Tool;
- archive executable Python for historical replay;
- make old Runtime bindings dynamically loadable;
- add a business Agent or domain rule.

## Acceptance

The deterministic acceptance creates three completed `reference-research-agent` Runs through the shared generic MCP execution path. One valid Run evaluates successfully. A Run with a tampered recorded binding and a Run evaluated after controlled current-Runtime drift both fail with `RUNTIME_BINDING_DRIFT`. Exactly one Evaluation is persisted, all three Artifacts remain intact, and References remain unchanged.
