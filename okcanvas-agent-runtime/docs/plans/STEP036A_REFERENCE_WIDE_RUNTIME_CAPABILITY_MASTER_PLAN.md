# STEP036A — Reference-wide Agent Runtime capability master plan

## Status

`CODE_AUDITED_PLAN_COMPLETE_STEP036_WINDOWS_LIVE_ACCEPTED_STEP037_STARTED`

This is a planning addendum to STEP036, not STEP037 implementation. Its sub-Agent sequence is
refined by `STEP036B_SUB_AGENT_INVOCATION_AND_WORKSPACE_ISOLATION.md`. The audit was completed while the executable baseline was `2.16.0`. STEP036 is now Windows live accepted and STEP037 implements the first executable walking-skeleton surface.

## 1. Objective

Replace the previous open-ended next-gap audit with one authoritative, code-derived build order for
the reusable Agent Runtime. The plan covers every retained reference tree and classifies the
OpenAI Agents SDK examples by capability rather than copying files one by one.

## 2. Binding development method

Use a **governed walking skeleton**.

Each P0 capability STEP must include:

1. an explicit product-owned declarative definition or closed registry;
2. direct use of the installed `openai-agents==0.19.0` primitive identified in this plan;
3. Runtime-binding coverage for every executable implementation and nested Agent dependency;
4. Product Task/Run/Event integration;
5. one positive case and one exact fail-closed case;
6. a visible execution result in the run-submitter surface;
7. deterministic acceptance and one Windows live closure when a real SDK/model path is material;
8. no dynamic executable plugin import;
9. no unrelated domain expansion;
10. no exhaustive edge matrix until the integrated P0 skeleton exists, unless a confirmed defect
    can corrupt state, leak authority, or duplicate external execution.

## 3. P0 sequence — basic Runtime skeleton

### STEP037 — Interactive Agent Runner foundation

**Purpose**

Make the current Runtime visible before adding more capabilities.

**Use existing capabilities only**

- coding Agent;
- reference-research MCP Agent;
- controlled local Tool approval Agent;
- replenishment Agent as a regression example.

**Product surface**

Create a separate local run-submitter surface, not a mutation mode in the read-only Operations
Console and not a replacement for the Approval Operator.

Minimum flow:

```text
select allowlisted Agent
→ enter request
→ create preflight
→ exact confirmation
→ observe persisted Events
→ open final Artifact
→ request recorded Evaluation
```

**Reference paths**

- `openai-cs-agents-demo/ui/components/chatkit-panel.tsx` — adapt event visibility only;
- `openai-cs-agents-demo/python-backend/server.py` — adapt Agent/tool/handoff presentation only;
- `openai-agents-streaming-api/src/api/utils/agent_router.py` — adapt endpoint/event envelope ideas;
- current `src/okcanvas_agent_runtime/operations_console/` — reuse read-only components where safe.

**Must reject**

- arbitrary Agent IDs;
- direct unconfirmed execution;
- approval decisions in this surface;
- raw secret/input rendering;
- in-memory Product state.

**Acceptance**

Four existing Agent paths launch through one surface without changing their existing execution
contracts. This STEP does not yet claim token-delta SDK streaming.

### STEP038 — Generic Function Tool Runtime V1

**Purpose**

Replace specialized Tool branches with a closed product-owned Tool Runtime registry.

**SDK primitive**

- `src/agents/tool.py`;
- `src/agents/decorators.py`;
- `tests/test_function_tool.py`;
- `tests/test_function_tool_decorator.py`;
- `tests/test_tool_context.py`;
- `tests/test_tool_identity.py`.

**Minimum proof**

- one deterministic read-only Function Tool without approval;
- the existing `local_text_metrics` approval-required Tool through the same registry;
- exact input/output contracts;
- Tool implementation and policy included in Runtime binding;
- arguments and results not persisted unless explicitly allowed.

**Not in scope**

Shell, Web, File Search, Code Interpreter, Computer Use, dynamic tool discovery, and Tool Search.

### STEP039 — SDK Streaming Event Adapter V1

**Purpose**

Expose actual `Runner.run_streamed()` execution while preserving Product Event rules.

**SDK primitive**

- `src/agents/run.py::Runner.run_streamed`;
- `src/agents/stream_events.py`;
- `src/agents/run_internal/streaming.py`;
- `examples/basic/stream_text.py`;
- `examples/basic/stream_items.py`;
- `tests/test_agent_runner_streamed.py`;
- `tests/test_stream_events.py`;
- `tests/test_streamed_terminal_output_backfill.py`;
- `tests/test_cancel_streaming.py`.

**Stream contract**

- ephemeral model text deltas;
- normalized Tool item progress;
- current Agent change notifications;
- final output and Artifact link;
- persisted canonical Events remain the replay source;
- raw deltas are not persisted by default.

**Failure contract**

Client disconnect does not cancel or duplicate Product execution unless a later explicit
cancellation policy is added.

### STEP040 — Sub-Agent Invocation Scope Foundation

**Purpose**

Establish product-owned parent/child invocation identity before native Handoff or Agent-as-Tool is
allowed. This STEP is defined by
`docs/plans/STEP036B_SUB_AGENT_INVOCATION_AND_WORKSPACE_ISOLATION.md`.

**Minimum proof**

- distinct root, HANDOFF-child, and AGENT_AS_TOOL-child invocation records;
- exact parent relationships and bounded nesting;
- closed child Agent definition graph included in Runtime binding;
- `workspace_access=none` as the default and no physical folder for language-only Agents;
- Runtime-generated distinct workspace roots demonstrated only as a deterministic policy fixture;
- no model filesystem capability, native Handoff, or Agent-as-Tool execution yet;
- unresolved target, self-loop, model-selected workspace path, and writable-root sharing rejected.

**Code-derived reason**

Native Handoff creates no folder, and `Agent.as_tool()` inherits the parent `run_config` unless a
separate one is supplied. Product isolation must therefore precede both capabilities.

### STEP041 — Handoff Runtime V1

**Purpose**

Add one native SDK Handoff and prove routing without inventing a Router engine.

**SDK primitive**

- `src/agents/handoffs/`;
- `src/agents/agent.py` Handoff fields;
- `examples/agent_patterns/routing.py`;
- `examples/handoffs/message_filter.py`;
- `tests/test_handoff_tool.py`;
- `tests/test_handoff_history_duplication.py`;
- `tests/test_handoff_prompt.py`.

**Minimum graph**

```text
triage-agent
→ one of two specialist Agents
→ final structured output
```

**Product contracts**

- closed Handoff target IDs;
- graph closure included in Runtime binding;
- `agent.handoff` canonical Event with from/to definition identity;
- max Handoff count;
- self-loop and unresolved target rejection;
- Session remains disabled in this first slice.

### STEP042 — Agent-as-Tool Runtime V1

**Purpose**

Add controlled delegation where the parent Agent retains control.

**SDK primitive**

- `src/agents/agent.py::Agent.as_tool`;
- `examples/agent_patterns/agents_as_tools.py`;
- `examples/agent_patterns/agents_as_tools_structured.py`;
- `examples/agent_patterns/agents_as_tools_streaming.py`;
- `tests/test_agent_as_tool.py`;
- `tests/test_agent_tool_input.py`;
- `tests/test_agent_tool_state.py`.

**Minimum graph**

```text
manager-agent
→ specialist Agent as Tool
→ manager final structured output
```

**Product contracts**

- child Agent definition and Runtime binding included in parent binding closure;
- bounded nested depth;
- nested invocation ID and parent Run evidence;
- no independent replacement Product Run in V1 unless code audit proves it is required;
- nested stream events visible through STEP039 adapter;
- Session and approval disabled for the first Agent-as-Tool slice.

### STEP043 — SQLite Session Runtime V1

**Purpose**

Enable two-turn conversation continuity through the SDK Session contract.

**SDK primitive**

- `src/agents/memory/session.py`;
- `src/agents/memory/sqlite_session.py`;
- `src/agents/run_internal/session_persistence.py`;
- `examples/memory/sqlite_session_example.py`;
- `tests/memory/test_session.py`;
- `tests/memory/test_session_limit.py`;
- `tests/memory/test_session_persistence_sanitize.py`.

**Minimum flow**

```text
create Product session
→ turn 1 Run
→ turn 2 Run with prior context
→ list bounded history metadata
→ clear session
```

**Product contracts**

- explicit session ID and owner authority;
- SQLite backend only;
- Session implementation/settings included in Runtime binding;
- raw history is not copied into Product Event payloads;
- one active turn per Session in V1;
- Handoff and approval remain disabled for this first Session slice.

### STEP044 — Guardrail Runtime V1

**Purpose**

Productize native SDK Guardrails rather than conflating them with Pydantic or policy validation.

**SDK primitive**

- `src/agents/guardrail.py`;
- `src/agents/tool_guardrails.py`;
- `examples/agent_patterns/input_guardrails.py`;
- `examples/agent_patterns/output_guardrails.py`;
- `examples/basic/tool_guardrails.py`;
- `tests/test_guardrails.py`;
- `tests/test_tool_guardrails.py`;
- `tests/test_output_guardrail_cancellation.py`;
- `tests/test_stream_input_guardrail_timing.py`.

**Minimum proof**

- one input Guardrail tripwire;
- one output Guardrail tripwire;
- one Tool-input or Tool-output Guardrail;
- exact Product terminal error codes;
- no Artifact on rejected output;
- Guardrail implementation included in Runtime binding;
- safe Event metadata without raw sensitive content.

### STEP045 — Integrated Runtime walking-skeleton acceptance

**Purpose**

Declare the basic Agent Runtime skeleton only after one integrated surface demonstrates all P0
capabilities.

**Required selectable scenarios**

1. tool-free structured Agent;
2. read-only Function Tool;
3. approval-required Function Tool;
4. local read-only MCP Agent;
5. SDK streaming output;
6. Handoff routing;
7. Agent-as-Tool delegation;
8. two-turn SQLite Session;
9. Guardrail rejection;
10. Artifact and recorded Evaluation;
11. visible root/child invocation identity and no implicit writable workspace sharing.

**Completion gate**

- all scenarios launched from the Interactive Runner;
- current Agent, Tool/MCP progress, approval interruption, final output, Artifact, and Evaluation
  are visible;
- every executable closure is Runtime-bound;
- Product and protected-payload invariants remain intact;
- one complete Windows live acceptance;
- documentation declares `BASIC_AGENT_RUNTIME_SKELETON_COMPLETE` only here;
- the STEP036B sub-Agent isolation constitution is satisfied.

## 4. P1 sequence — breadth after skeleton

The following are ordered candidates, not pre-authorized implementation STEPs.

### P1-A — MCP breadth

- Streamable HTTP transport first, then SSE only if required;
- static/dynamic Tool filtering;
- prompts and resources as read-only capabilities;
- MCP approval only after generic Tool approval composition is shared;
- references: `examples/mcp/**`, `tests/mcp/**`.

### P1-B — Session hardening

- Session + Handoff history;
- Session + RunState approval interruption;
- compaction;
- encrypted Session wrapper;
- references: `examples/memory/hitl_session_scenario.py`, compaction and encrypted examples,
  `tests/test_hitl_session_scenario.py`.

### P1-C — Bounded orchestration

- parent/child Product Run model;
- bounded parallel fan-out;
- cancellation and partial failure;
- deterministic aggregation;
- optional evaluator/judge Agent;
- references: `examples/agent_patterns/parallelization.py`, research and financial managers,
  `examples/agent_patterns/llm_as_a_judge.py`.

### P1-D — Model policy

- explicit retry policy separate from product replay;
- reasoning-content evidence policy;
- optional second provider only after contract parity tests;
- references: `src/agents/retry.py`, model tests, `examples/model_providers/**`,
  `examples/reasoning_content/**`.

### P1-E — Selective hosted read-only tools

Evaluate Web Search and File Search separately. Code Interpreter, Shell, Apply Patch, Computer Use,
Image Generation, Programmatic Tool Calling, and Tool Search require separate authority and
retention designs and are not grouped into one Tool STEP.

## 5. P2/P3 independent tracks

### Sandbox/Codex track

Use `src/agents/sandbox/**`, `examples/sandbox/**`, and the 44 sandbox tests as a separate
workspace-execution product track. Do not merge the sandbox manifest/session/mount/provider model
into the basic Agent Runtime registry prematurely. Existing controlled Codex slices remain valid
regression assets.

### Distributed durability track

Use the Temporal reference only when local explicit reconciliation and a single-node SQLite store
no longer meet deployment requirements. Temporal workflow/activity retries must not silently
replace existing confirmation, Runtime binding, or no-reexecution constitutions.

### Realtime and voice track

Realtime Runner/session and VoicePipeline are separate modality products. They begin only after the
text Runtime skeleton and its authorization/session model are stable.

### External Session backends

Redis, MongoDB, Dapr, SQLAlchemy, and OpenAI-hosted Session implementations follow the SQLite
contract. No multi-backend abstraction is created before SQLite live acceptance.

## 6. Reference-specific adoption record

### OpenAI Agents Python 0.19.0

- ADOPT installed SDK primitives;
- ADAPT through closed product registries, bindings, Product state, and safe stream envelopes;
- REJECT direct imports from `/reference` and arbitrary dynamic plugins.

### Temporal Agents demos

- ADAPT workflow status/query/update concepts later;
- DEFER Temporal worker/plugin dependency;
- REJECT automatic activity retry as a substitute for governed Agent replay policy.

### OpenAI customer-service demo

- ADAPT Handoff graph display, guardrail display, and progress-panel UX;
- REJECT `MemoryStore` as durable state and demo context mutation as authority.

### OpenAI Agents streaming API

- ADAPT event formatting and endpoint ergonomics;
- REJECT broad exception swallowing, implicit environment-enabled sessions, and direct use as the
  Product persistence layer.

## 7. Change-control rule

STEP036 is Windows live accepted and STEP037 is implemented as listed above. Before STEP038, close STEP037 on Windows unless a fresh code audit identifies a
state-corruption, authority-leak, or duplicate-external-execution defect that blocks it. Ordinary
missing edge cases do not postpone the walking skeleton.

No later STEP number in this plan is considered implemented or authorized merely because it is
listed here.
