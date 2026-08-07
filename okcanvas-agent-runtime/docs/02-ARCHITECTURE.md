# Architecture Baseline

The current runtime is an evidence-first Python modular monolith. The OpenAI Agents SDK supplies the Agent execution mechanics; OKCanvas supplies durable product state, policy, evidence, and operating interfaces.

See:

- `docs/06-REFERENCE-ADOPTION-MATRIX.md`;
- `docs/07-TARGET-PLATFORM-ARCHITECTURE.md`;
- `docs/08-SERVICE-BOUNDARIES.md`;
- `docs/09-DELIVERY-ROADMAP.md`.

## Current accepted execution slices

```text
STEP002
controlled fixture -> Codex read-only -> events/thread/evidence -> no mutation

STEP003
source fixture -> disposable Git copy -> Codex minimal write
              -> independent pytest validator -> patch/evidence -> copy disposal
```

STEP004 adds SDK-native whole-run approval around STEP003 but is not yet live accepted.

## Governing boundaries

```text
Product state
  Task / Run / Event / Approval / Artifact / Validation
  owned by OKCanvas

SDK adapter state
  Session / RunState / SDK stream events / Trace
  referenced by OKCanvas product records

Optional integration state
  Codex Thread / MCP connection / future PlanVM execution ID
  referenced by a Run, never the Run itself
```

## Directory boundaries

- `reference/`: immutable upstream source and findings.
- `specs/agents/`: declarative Agent definitions and evaluations.
- `specs/tools/`: Tool contracts and policy.
- `specs/mcp/`: future MCP contracts and policy.
- `specs/runtime/`: product-level Task, Run, Event, Approval, Artifact, and Validation plans.
- `src/okcanvas_agent_runtime/`: executable implementation.
- `fixtures/`: controlled local acceptance repositories.
- `tests/`: our tests only; upstream tests are not collected.

## Current architecture direction

Codex remains an optional specialized adapter. The core product path now owns durable Task, Run, Event, Artifact, deterministic Evaluation, and local-admin API boundaries. STEP012 closes the execution-to-evaluation loop using only product-owned evidence; SDK `RunResult` objects are not product persistence.
