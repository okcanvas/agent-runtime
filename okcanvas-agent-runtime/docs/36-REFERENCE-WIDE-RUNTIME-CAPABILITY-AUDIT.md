# Reference-wide Agent Runtime capability audit

## 1. Scope and method

This audit was produced from the immutable trees declared in `reference/MANIFEST.json`.
It is not a roadmap inferred from example names. The audit inspected source modules, examples,
tests, and integration adapters across all four retained references.

| Reference | Classification | Files inspected | Primary use |
|---|---|---:|---|
| `openai-agents-python-0.19.0` | primary SDK source | 1,419 | Agent, Runner, tools, Handoff, Session, streaming, MCP, sandbox, realtime, voice |
| `temporal-openai-agents-demos` | durability example | 36 | durable workflow/activity orchestration and interaction signals |
| `openai-cs-agents-demo` | UX and Handoff example | 43 | Handoff graph, guardrails, ChatKit presentation, mutable demo context |
| `openai-agents-streaming-api` | adapter and negative example | 38 | REST/SSE adapter shapes, SQLiteSession convenience, research orchestration |

The primary SDK snapshot contains:

- 302 files below `src/agents/`, including 294 Python files;
- 307 files below `examples/`, including 216 Python files;
- 297 files below `tests/`, including 296 Python files.

Every retained file and its audit category is recorded in
`docs/reference/STEP036A_REFERENCE_CAPABILITY_INVENTORY.json` with SHA-256.

## 2. Code-derived architectural facts

### 2.1 `Agent` is already the capability composition root

`src/agents/agent.py` owns the native composition points:

- `tools`;
- `mcp_servers`;
- `handoffs`;
- input and output guardrails;
- structured `output_type`;
- `Agent.as_tool()` for nested Agent delegation.

OKCanvas should not create a second unrelated composition language. Product-owned declarative
specifications should resolve into these SDK primitives through closed registries and Runtime
bindings.

### 2.2 Routing is Handoff, not a separate SDK router

`examples/agent_patterns/routing.py` defines a triage Agent with three Handoffs, calls
`Runner.run_streamed()`, and continues from `result.current_agent`. There is no independent Router
runtime in this example. The product sequence must therefore implement governed Handoff before
claiming routing support.

### 2.3 Parallelization is application orchestration

`examples/agent_patterns/parallelization.py`, `examples/research_bot/manager.py`, and
`examples/financial_research_agent/manager.py` use `asyncio.gather`, `asyncio.create_task`, and
`asyncio.as_completed` around multiple `Runner.run()` calls. Parallelization is not a separate
Agents SDK execution primitive. OKCanvas should not build a generic parallel engine before it has
child-Run identity, bounded fan-out, cancellation, and result aggregation contracts.

### 2.4 Agent-as-Tool depends on the Function Tool substrate

`Agent.as_tool()` in `src/agents/agent.py` returns a Function Tool that invokes a nested Runner. It
supports an optional Session, approval, output extraction, hooks, and nested streaming callbacks.
The examples under `examples/agent_patterns/agents_as_tools*.py` confirm that this capability must
be built after a generic Function Tool Runtime and stream-event adapter.

### 2.5 Session is a Runner concern and intersects interruption/resume

`Runner.run()`, `run_sync()`, and `run_streamed()` accept a `Session`. The implementation in
`src/agents/run.py` performs session input preparation and result persistence. The tests under
`tests/memory/`, `tests/test_hitl_session_scenario.py`, and `tests/test_run_impl_resume_paths.py`
show that Session, Handoff history, and RunState resume interact. The first Session slice must be
SQLite-only and must not be combined with Handoff or approval in the same first STEP.

### 2.6 Streaming has three different meanings

The reference distinguishes:

1. model response deltas through `RawResponsesStreamEvent`;
2. normalized run items through `RunItemStreamEvent`;
3. current-Agent changes through `AgentUpdatedStreamEvent`.

OKCanvas currently has persisted Product Event SSE, which is replayable, but it does not expose
SDK token/item/agent streams. The product must keep ephemeral sensitive deltas separate from
persisted canonical Events.

### 2.7 Guardrails are separate from schema validation

The SDK provides input, output, tool-input, and tool-output guardrails. Their tripwires have
specific interruption and cancellation behavior, covered by `tests/test_guardrails.py`,
`tests/test_tool_guardrails.py`, `tests/test_output_guardrail_cancellation.py`, and
`tests/test_stream_input_guardrail_timing.py`. Pydantic output validation and product policy checks
must not be mislabeled as SDK Guardrails.

### 2.8 MCP is broader than the current local stdio slice

The primary source supports stdio, SSE, and Streamable HTTP servers, manager lifecycle, tool
caching, retries, filtering, prompts, resources, approval, and session IDs. Current OKCanvas
supports one allowlisted local stdio read-only MCP server. Remote transport, resources/prompts,
and MCP approval are later expansions, not prerequisites for the basic Runtime skeleton.

### 2.9 Sandbox, realtime, and voice are separate product tracks

The sandbox tree has its own manifest, snapshot, capability, mount, session, memory, and provider
abstractions and 44 dedicated test files. Realtime and voice also have distinct Runner/session
stacks. They should not be inserted into the basic text Agent skeleton.

### 2.10 The secondary references are adaptation sources, not foundations

- Temporal demonstrates workflow/activity durability and interaction signals, but introduces an
  external workflow engine and retry semantics. It is a later distributed-runtime reference.
- The customer-service demo demonstrates Handoffs, guardrails, tool/context updates, and a useful
  event UI, but `python-backend/memory_store.py` is explicitly in-memory demo persistence.
- The streaming API demonstrates reusable FastAPI/SSE formatting and SQLiteSession convenience,
  but its generic adapter catches broad exceptions and environment-driven session defaults. It is
  not a fail-closed Product state base.

## 3. Current OKCanvas capability position

| Capability | Current state | Evidence in current code | Audit disposition |
|---|---|---|---|
| Tool-free structured Agent | supported/live | generic execution, output registry, Artifact | retain |
| Lifecycle hooks and usage | supported | normalized Agent/model/Tool Events and token metadata | retain |
| Invalid final-output recovery | supported, contract-specific | output-contract Runtime registry | retain, never universalize |
| RunState approval/resume | supported/live for controlled Tool | encrypted state and operator approval | retain |
| Product Task/Run/Event/Artifact | supported | SQLite Product store and Control API | retain |
| Runtime binding and drift checks | supported | STEP033 and STEP036 | mandatory for every new capability |
| Read-only local MCP | supported/live | reference-catalog stdio MCP | retain |
| Persisted SSE | supported | canonical Event cursor stream | retain; not equivalent to SDK streaming |
| Generic Function Tool registry | absent | only specialized Tool paths | P0 skeleton |
| SDK streaming adapter | absent | generic Gateway uses `Runner.run()` | P0 skeleton |
| Handoff | explicitly disabled | Agent catalog accepts `session_mode=disabled`; Gateway passes `handoffs=[]` | P0 skeleton |
| Agent-as-Tool | absent | no nested Agent registry or binding closure | P0 skeleton |
| SDK Session | explicitly disabled | no Session store/binding | P0 skeleton |
| SDK Guardrails | absent as product capability | no declarative guardrail registry | P0 skeleton |
| Interactive Runner | absent | Operations Console is read-only observation | P0 skeleton |
| Parallel orchestration | absent | no child-Run/fan-out contract | P1 after skeleton |
| MCP remote transports/resources/prompts | absent | local stdio Tool use only | P1 |
| Session compaction/encryption/external backends | absent | no Session capability | P1/P2 |
| Model providers/retry policy | mostly absent | OpenAI pinned path, product-level failures only | P1/P2 |
| Hosted tools | absent | no Web/File/Code/Computer hosted capability | selective P1/P2 |
| Sandbox Runtime | controlled Codex slices only | no general SDK sandbox composition | separate P2 track |
| Realtime and voice | absent | no realtime or audio surface | P3 |
| Temporal/distributed workflows | absent | local explicit reconciliation instead | P3 unless scale requires it |

## 4. Adopt, adapt, defer, reject

### Adopt through the installed SDK

- `Agent`, `Runner`, `RunState`, `RunConfig`, hooks, output schemas;
- `function_tool` / `Agent.as_tool()`;
- native Handoffs;
- `Runner.run_streamed()` event types;
- `SQLiteSession` for the first Session slice;
- SDK Guardrail primitives;
- existing MCP classes through product-owned definitions.

### Adapt behind product-owned contracts

- Agent/Tool/Handoff/Session registries;
- Runtime binding closure for nested Agents and capability implementations;
- stream envelopes and persistence policy;
- child/nested invocation evidence;
- guardrail failure mapping;
- Interactive Runner authorization and UX;
- customer-service event visualization ideas;
- FastAPI/SSE adapter ergonomics.

### Defer

- parallel fan-out and manager workflows;
- remote MCP transports and MCP resources/prompts;
- Session compaction, encryption, Redis, MongoDB, Dapr, SQLAlchemy;
- alternate model providers and model retry policy;
- hosted Web/File/Code/Image tools;
- sandbox provider marketplace;
- Temporal workers;
- realtime and voice.

### Reject for the basic Runtime

- copying all examples as product features;
- dynamic import of arbitrary Agent/Tool Python from specifications;
- demo in-memory stores as durable state;
- implicit environment-enabled Session behavior;
- broad exception swallowing in generic API adapters;
- treating application `asyncio.gather` as a native parallel Agent engine;
- combining Handoff, Session, approval, remote MCP, and UI in one first implementation;
- storing raw model deltas as canonical Product Events by default.

## 5. Planning conclusion

The previous depth-first sequence produced a strong governed single-Agent spine. Continuing only
with hidden integrity work would delay the actual Runtime shape. Creating empty interfaces for all
SDK features would create a speculative platform. The selected method is a governed walking
skeleton:

1. expose the existing spine through a separate run-submitter Interactive Runner;
2. add one SDK capability at a time through its actual upstream primitive;
3. require one positive and one fail-closed slice, Product state, Runtime binding, and visible
   execution evidence;
4. defer exhaustive hardening until the P0 capability set is connected;
5. finish with one integrated Windows live showcase before declaring the basic skeleton complete.

The authoritative sequence and acceptance gates are in
`docs/plans/STEP036A_REFERENCE_WIDE_RUNTIME_CAPABILITY_MASTER_PLAN.md`.
## 9. STEP036B correction — sub-Agent isolation is product-owned

Further code inspection of `Agent.as_tool()`, native Handoff, and `agents.sandbox` established:

- Handoff transfers control/history but allocates no filesystem workspace.
- Agent-as-Tool uses a nested Runner and inherits parent `run_config` unless explicitly overridden.
- A separate SDK Sandbox workspace exists only when the caller creates and supplies a distinct `SandboxSession`.
- The current OKCanvas AgentDefinitionCatalog already isolates definition directories and forbids symlink/path escape, but it has no child invocation identity or workspace policy yet.

The P0 order is therefore revised to insert STEP040 Sub-Agent Invocation Scope Foundation before native Handoff and Agent-as-Tool. Definition and invocation isolation are mandatory for every child. A physical workspace is mandatory only when filesystem capability is granted, and file-capable parent/child invocations may not share one writable root by default. The binding constitution is `docs/plans/STEP036B_SUB_AGENT_INVOCATION_AND_WORKSPACE_ISOLATION.md`.

