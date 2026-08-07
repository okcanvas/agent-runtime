# STEP062 Code Audit — Bounded Multi-Agent Orchestration Foundation

## Accepted predecessor evidence

The user ran `sh_run_step061_acceptance` on Windows and reported `PASSED` with all `20/20` checks.
The accepted matrix contains 212 classified examples across 15 areas with counts:

```text
ADOPT 16
ADAPT 16
DEFER 171
REJECT 9
```

The result and every reported check are retained in
`docs/evidence/STEP061_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`. The matrix selected STEP062 as the
single next implementation scope.

## Pre-implementation code audit

### Existing child primitives were not orchestration

Before STEP062, `src/okcanvas_agent_runtime/execution/openai_gateway.py` supported one immutable
native Handoff or one immutable Agent-as-Tool edge. The invocation policy limited each path to one
child and depth one. There was no sibling fan-out, sibling cancellation, partial-failure policy or
deterministic aggregate output contract.

### Existing Product authorities were reusable

The following existing authorities were retained rather than replaced:

- `GenericAgentExecutionService` for one Product Task/Run lifecycle;
- `AgentRuntimeBindingCatalog` for immutable executable identity;
- `InvocationScopeService` and the SQLite invocation ledger for parent/child identity and usage;
- lifecycle Events for ordered safe observability;
- output registry plus Artifact verification for strict final output;
- immutable model route, zero retry, reasoning evidence, storage and provider-ID policies.

Therefore STEP062 adds an execution path, not a second workflow database or orchestration service.

## Implemented files and responsibilities

### Orchestration contract package

`src/okcanvas_agent_runtime/orchestration/models.py`

- immutable `BoundedOrchestrationPolicy`;
- strict child aggregate item with ordinal, Agent ID, result and usage;
- strict `BoundedOrchestrationResult`;
- validators for exact two-child declaration order, unique IDs, severity aggregation and exact
  product-generated summary.

`src/okcanvas_agent_runtime/orchestration/policy.py`

- reads only `specs/runtime/bounded-orchestration-policy.json`;
- rejects missing, symlinked, escaped, malformed, extra-key or value-drifted policy files;
- binds raw policy SHA-256.

`src/okcanvas_agent_runtime/orchestration/runtime.py`

- validates root and terminal child Agent definitions;
- sums all usage dimensions;
- aggregates child results by ordinal independent of completion order.

`src/okcanvas_agent_runtime/orchestration/openai_runtime.py`

- resolves the two immutable child definitions;
- creates only the two child SDK Agents;
- creates two `asyncio` tasks and waits with `FIRST_EXCEPTION`;
- cancels pending siblings on the first runtime failure;
- emits safe orchestration lifecycle Events;
- invokes direct `Runner.run()` exactly twice;
- returns no provider response ID;
- closes the pinned model provider in `finally`.

### Definitions and immutable policy

- `specs/agents/bounded-orchestration-manager-agent/`;
- `specs/agents/bounded-orchestration-architecture-agent/`;
- `specs/agents/bounded-orchestration-risk-agent/`;
- `specs/runtime/bounded-orchestration-policy.json`.

The root output contract is `BoundedOrchestrationResult`. Both children use `CodingAgentResult`.
All three are Session-disabled, workspace-free and have no Tool, MCP, Handoff, Agent-as-Tool or
Guardrail declarations.

### Definition and graph enforcement

`src/okcanvas_agent_runtime/agent_definitions/catalog.py` accepts the optional
`orchestration_children` key but permits it only as exactly two distinct children on a completely
capability-free root. It rejects Session, workspace, Guardrail and every other child/capability
family on that root.

`src/okcanvas_agent_runtime/invocations/graph.py` adds immutable
`ORCHESTRATION_CHILD` edges, allows only the exact two sibling edges and keeps every child terminal.

### Runtime binding

`src/okcanvas_agent_runtime/execution/runtime_binding.py` selects
`bounded-multi-agent-orchestration-v1` only after policy and definition validation. The root binding
includes:

- orchestration policy payload and policy SHA;
- combined orchestration implementation SHA;
- declaration ordinal for each child;
- child definition version and SHA;
- each independently resolved child Runtime binding SHA;
- existing invocation policy and execution engine SHAs.

Any policy, implementation, root, child or child binding change therefore changes the root Runtime
binding and invalidates prior confirmation identity.

### Product invocation ledger

`InvocationKind.ORCHESTRATION_CHILD` is stored in the existing TEXT-backed SQLite invocation kind
column; no database migration is required. The Product service plans both child rows before SDK
execution and maps lifecycle ordinal plus Agent ID back to the immutable Invocation identity.

Allowed transitions are:

```text
ROOT: RUNNING → SUCCEEDED | FAILED | CANCELLED
child success: PLANNED → RUNNING → SUCCEEDED
child failure: PLANNED → RUNNING → FAILED
pending sibling: PLANNED | RUNNING → CANCELLED
```

On successful orchestration, root usage is exactly zero. On terminal Product failure, any remaining
planned child is cancelled and any remaining running child is failed unless the Product Run itself
was cancelled.

### Deterministic aggregate

Completion order is intentionally not authoritative. The aggregate sorts child results by immutable
ordinal, computes the maximum business severity and generates:

```text
2/2 specialists completed; aggregate status <PASS|PARTIAL|FAIL>.
```

The complete child structured outputs are retained only inside the verified aggregate Artifact, not
inside lifecycle Events.

### Public visibility

- Control API contracts now expose `orchestration_children`.
- Interactive runner displays `ORCHESTRATION:<child-id>` chips.
- Node CLI treats exactly two fixed, capability-free orchestration children as compatible, renders
  aggregate child summaries and safe progress Events.
- Run submission classifies the exact runtime path as governed read-only execution.

## Tested invariants

`tests/test_bounded_multi_agent_orchestration.py` proves:

- exact policy, graph and binding;
- direct overlapping sibling execution with maximum concurrency two;
- no Session and no streamed root path;
- one shared trace/group identity with distinct child ordinals;
- reverse completion and declaration-order aggregation;
- exact sum of request, input, output, total, cached and reasoning usage;
- successful Product ledger and one Artifact;
- failed/cancelled child ledger and zero Artifacts.

`tests/test_step062_bounded_multi_agent_orchestration_baseline.py` binds the RuntimeInfo flags,
public API field, required source/document set and current baseline.

## Explicitly unresolved

- real OpenAI Windows execution has not been reported for STEP062;
- cancellation can request cancellation of an in-flight SDK task, but remote provider work may have
  already consumed tokens before cooperative cancellation completes;
- failed-child usage is limited to usage available from the raised Product failure or already
  completed lifecycle accounting;
- no collect-partial policy exists;
- no variable child count, nested graph, planner, verifier/writer stage or LLM judge exists;
- no STEP063 is selected in this package.
