# STEP062 — Bounded Multi-Agent Orchestration Foundation

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

- Project: `okcanvas-agent-runtime`
- Version: `2.42.0`
- STEP: `STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION`
- Predecessor: STEP061 Windows live accepted from the user-reported 20/20 result.

## Objective

Add the first product-owned multi-Agent execution primitive without introducing an unbounded
workflow engine. One immutable root definition owns exactly two terminal language-only specialist
Agents. Product Runtime code starts both siblings concurrently, records each as a child Invocation,
and creates one deterministic aggregate Artifact only when both required children succeed.

## Closed V1 graph

```text
bounded-orchestration-manager-agent       logical root; model calls 0
├─ bounded-orchestration-architecture-agent   Runner.run; ordinal 1
└─ bounded-orchestration-risk-agent           Runner.run; ordinal 2

both successful
→ product-owned declaration-order aggregation
→ BoundedOrchestrationResult
→ one verified root Artifact
```

The manager is not instantiated as an SDK `Agent`. It is a Product Runtime authority that binds the
closed graph, lifecycle, invocation identities, failure policy and aggregate output.

## Immutable policy

`specs/runtime/bounded-orchestration-policy.json` fixes:

- child count: `2`;
- maximum parallelism: `2`;
- maximum depth: `1`;
- failure mode: `ALL_REQUIRED_FAIL_FAST`;
- cancellation mode: `CANCEL_PENDING_SIBLINGS`;
- aggregation mode: `DECLARATION_ORDER_STRUCTURED`;
- child output: `CodingAgentResult`;
- root output: `BoundedOrchestrationResult`;
- child Session: disabled;
- workspace: none;
- native child streaming: disabled;
- Tool/MCP/Handoff/Agent-as-Tool/Guardrail capabilities: none.

## Runtime behavior

1. The existing Product Task and Run are created once.
2. One ROOT Invocation is created with zero model usage.
3. Two `ORCHESTRATION_CHILD` Invocations are planned in the immutable declaration order.
4. Both child start lifecycle events are persisted before the two asynchronous SDK tasks begin.
5. Each child executes one independent `Runner.run()` with its own SDK Agent and RunConfig, the
   same Product Run group ID and the same trace ID.
6. Child outputs are strict `CodingAgentResult` values and child usage is recorded independently.
7. Completion order may differ from declaration order. Aggregation always sorts by ordinal `1,2`.
8. Aggregate business status is the maximum child severity `PASS < PARTIAL < FAIL`.
9. Root summary is product-generated using the exact deterministic format.
10. Run usage is the sum of both child usages; root Invocation usage remains zero.
11. Provider response/request identifiers and raw child output are not persisted in Events.
12. Exactly one aggregate Artifact is created on complete success.

## Failure boundary

If either child raises an execution failure:

- the failed child becomes `FAILED`;
- every unfinished sibling task receives cancellation;
- a cancelled sibling becomes `CANCELLED`;
- the ROOT Invocation and Product Run become `FAILED`;
- known child usage is summed and retained;
- no aggregate output and no Artifact are created;
- no partial-success mode exists in V1.

A child business result with status `FAIL` is still a structurally successful child execution. It is
included in the complete aggregate, whose business status then becomes `FAIL`. Runtime failure and
business severity remain distinct.

## Product/API/CLI visibility

- Agent definition APIs expose `orchestration_children`.
- Runtime binding exposes child declaration ordinal and each child Runtime binding SHA-256.
- Product Invocation APIs expose ROOT plus two `ORCHESTRATION_CHILD` rows.
- Node CLI identifies the fixed parallel specialist graph, renders child aggregate summaries, and
  shows safe child start/completion/failure/cancellation progress without raw content.
- Existing single-Agent, Session, Tool, Handoff, Agent-as-Tool, MCP and Guardrail paths retain their
  prior behavior.

## Explicit exclusions

STEP062 does not add:

- dynamic child discovery or planner-generated child work;
- more than two children or depth greater than one;
- collect-partial execution;
- LLM judge or model-owned aggregation;
- root manager model call;
- native streamed child deltas;
- Session, compaction or encryption;
- Function Tool, approval, MCP, hosted Tool or remote transport;
- filesystem, Shell, writable workspace or Sandbox;
- independent child Product Runs;
- retries or fallback models;
- a selected STEP063.

## Acceptance

Deterministic acceptance must prove:

1. current baseline and version are exact;
2. STEP061 Windows 20/20 closure is recorded;
3. immutable policy values and SHA are present;
4. the root declares exactly the two expected children;
5. all three definitions satisfy the capability-free graph contract;
6. Runtime binding selects `bounded-multi-agent-orchestration-v1`;
7. child binding entries are ordinals `1,2` with exact IDs and binding SHAs;
8. two SDK `Runner.run()` calls overlap with maximum observed concurrency `2`;
9. root SDK Agent calls are zero and native streaming calls are zero;
10. reverse child completion still produces declaration-order aggregate children;
11. child and total usage are exact;
12. one Product Run records exactly one ROOT and two child Invocations;
13. success creates one verified aggregate Artifact;
14. runtime child failure produces FAILED/CANCELLED children and no Artifact;
15. Control API and Node CLI expose orchestration safely;
16. Python, Node, TypeScript and immutable Reference regression gates pass.

No real OpenAI call is required for deterministic acceptance. Windows live acceptance remains
pending until the packaged `sh_run_step062_acceptance.cmd` result is reported.
