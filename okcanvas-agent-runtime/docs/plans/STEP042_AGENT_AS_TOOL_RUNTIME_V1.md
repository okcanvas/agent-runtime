# STEP042 — Agent-as-Tool Runtime V1

## Status

- Executable baseline: `okcanvas-agent-runtime 2.22.0`
- STEP: `STEP042_AGENT_AS_TOOL_RUNTIME_V1`
- Previous Windows closure: STEP041 Native Handoff Runtime V1
- Current state: implemented and deterministically accepted; Windows live rerun pending

## Why this STEP exists

STEP041 proved transfer of control: the active Agent changed from a parent to a specialist. Agent-as-Tool is a different execution shape. The parent remains the active coordinator, invokes a declared specialist as a Tool, receives a bounded result, and then produces the Product final output.

The upstream SDK implements this through `Agent.as_tool()`, which internally runs a nested Runner. It does not create Product invocation identity, separate usage attribution, workspace isolation, canonical evidence, or a second Product lifecycle. STEP042 closes those product-owned gaps without inventing a second child ledger.

## Exact execution shape

```text
one governed Submission
└─ one Product Task
   └─ one Product Run
      └─ ROOT: agent-tool-manager-agent
         ├─ invokes declared specialist through Agent.as_tool()
         ├─ AGENT_AS_TOOL: agent-tool-specialist-agent
         └─ resumes parent control and creates final output
```

## Runtime contract

V1 permits exactly one child call at depth one. The immutable policy is `specs/runtime/agent-as-tool-policy.json`:

- input mode: `MODEL_GENERATED_TEXT`;
- output mode: `BOUNDED_STRUCTURED_JSON`;
- maximum child result: 8,192 UTF-8 bytes;
- nested streaming: required;
- parent RunConfig inheritance: prohibited;
- parent and child output contract: equal;
- workspace access: `none`;
- Handoff, MCP, local Function Tool, Session and approval mixing: prohibited.

The parent definition declares exactly one child under `agent_tools`. The child is terminal and language-only. Model output may decide what bounded text to send to the already-declared specialist, but may not select another Agent definition or execution provider.

## Product invocation lifecycle

Before the nested Tool call:

```text
ROOT = RUNNING
```

At `agent.tool.started`:

1. verify the immutable ROOT→child graph;
2. require ROOT to remain `RUNNING`;
3. create exactly one `AGENT_AS_TOOL` child invocation;
4. transition the child to `RUNNING`;
5. retain parent control and the same Product Run.

At nested completion:

1. calculate child usage as the non-negative delta between cumulative SDK usage before and after the nested call;
2. terminalize the child `SUCCEEDED` with that usage;
3. emit safe `agent.tool.completed` evidence;
4. return bounded structured JSON to the parent;
5. keep ROOT active until the parent final output completes.

At final Product success:

```text
ROOT usage = final Product cumulative usage - child usage
ROOT = SUCCEEDED
Product Run = SUCCEEDED
```

A negative, inconsistent, repeated, undeclared, or over-limit child usage/lifecycle transition fails closed.

## Explicit child RunConfig

Upstream `Agent.as_tool()` falls back to `ToolContext.run_config` when no child RunConfig is supplied. STEP042 prohibits that implicit inheritance. Product code constructs and passes a child-specific RunConfig with safe trace metadata:

- Product Run identity;
- invocation kind `AGENT_AS_TOOL`;
- parent Agent ID;
- child Agent ID;
- `run_config_inherited=false`.

The child receives no Session and no failure fallback that could hide a nested failure.

## Streaming

The parent continues through `Runner.run_streamed()`. The nested Agent Tool uses SDK `on_stream` and the STEP039 product-owned adapter. Ephemeral nested event types are:

- `agent.tool.stream.started`;
- `agent.tool.agent.updated`;
- `agent.tool.model.text.delta`;
- `agent.tool.run.item`;
- `agent.tool.stream.completed`.

Only safe Agent identity, output text delta, and Run-item type/name metadata are exposed. Function-call arguments, child raw result/items, prompts, instructions, reasoning, Tool call IDs, secrets, and SDK raw objects are dropped. Native nested events are never inserted into the canonical Product Event ledger.

## Canonical evidence

STEP042 adds two canonical Event types:

- `agent.tool.started`;
- `agent.tool.completed`.

They persist only safe identity/policy/presence data, child definition and Runtime-binding evidence, workspace state, parent-control evidence, and child usage. Raw arguments and raw child results are explicitly marked not persisted.

## Runtime binding

The confirmation-bound Runtime fingerprint includes:

- Agent-as-Tool policy bytes and SHA;
- closed parent→child graph;
- parent and child Agent definitions;
- Agent Tool runtime implementation;
- invocation ledger/service implementation;
- explicit child RunConfig construction path;
- nested streaming adapter/broker path;
- output contract runtime and generic execution engine.

Any change requires a new preflight and exact confirmation.

## Workspace boundary

Both parent and child are language-only:

```text
workspace_access=none
workspace_ref=null
```

No host directory, writable parent root, filesystem capability, Shell, network, mount, Sandbox Session, or secret capability is allocated or inherited.

## Deterministic acceptance

`sh_run_step042_acceptance.cmd` must prove:

- all 29 checks true;
- `Agent.as_tool()` constructed once and invoked once;
- outer and nested streaming once each; non-streamed Runner zero;
- one Submission/Task/Run;
- exactly ROOT and AGENT_AS_TOOL invocations;
- both succeed with exact relationship and distinct namespaces;
- parent retains control after child completion;
- usage parent `23/7/30`, child `17/5/22`, Product total `40/12/52`;
- one canonical start and completion Event;
- explicit child RunConfig, no Session, no implicit inheritance;
- bounded structured child result;
- safe nested stream and no raw nested data;
- no workspace;
- one verified Artifact and one PASSED recorded Evaluation;
- successful protected payload deleted;
- final counts `1/1/1/2/18/1/1`;
- unchanged References and cleanup `COMPLETED`.

## Explicit non-scope

STEP042 does not implement:

- multiple Agent Tool calls;
- nested depth greater than one;
- Agent-as-Tool mixed with Handoff, MCP, local Function Tool, approval, or Session;
- child-specific Product Task/Run, Artifact, Evaluation, retention, or approval record;
- child filesystem workspace or Sandbox;
- child process-loss resume;
- parent/child parallel execution;
- arbitrary/dynamic Agent construction;
- child result larger than the bounded structured contract.

## Next STEP

`STEP043_SQLITE_SESSION_RUNTIME_V1`

It must introduce a local product-owned SQLite Session for a tool-free Agent only, prove two-turn continuity and clear, keep one active Turn per Session, and remain separate from Handoff, Agent-as-Tool, approval, workspace, compaction, and long-term memory.
