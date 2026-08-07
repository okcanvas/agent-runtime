# STEP040 — Sub-Agent Invocation Scope Foundation

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Executable baseline: `okcanvas-agent-runtime 2.20.0`.

STEP039 Native SDK Streaming Adapter is Windows live accepted. STEP040 is the identity and policy foundation required before STEP041 Native Handoff and STEP042 Agent-as-Tool.

## 1. Problem confirmed from code

The installed OpenAI Agents SDK can move control to another Agent or start a nested Agent, but it does not create the OKCanvas product identity needed to answer:

- which Agent invocation produced a state transition or usage amount;
- which invocation was the root, parent, Handoff child, or Agent-as-Tool child;
- whether a child was part of the immutable Agent-definition graph confirmed at preflight;
- whether nested depth and child counts stayed inside product policy;
- whether a language-only child received a filesystem workspace;
- which Runtime binding governed each invocation.

Native Handoff transfers input/history and changes the current SDK Agent. `Agent.as_tool()` starts a nested Runner and can inherit the parent `run_config`. Neither primitive creates a product-owned invocation ledger or a separate filesystem root.

## 2. Implemented product contracts

### 2.1 Immutable invocation policy

`specs/runtime/sub-agent-invocation-policy.json` defines:

- policy ID and version;
- maximum graph/invocation depth;
- maximum Handoff children per Product Run;
- maximum Agent-as-Tool children per Product Run;
- default `workspace_access=none`;
- `physical_workspace_enabled=false` for STEP040.

The policy is integrity-hashed and included in `AgentRuntimeBinding`.

### 2.2 Agent definition graph

Agent definitions now support optional:

- `agent_tools`: closed Agent-as-Tool target IDs;
- `workspace_access`: currently only `none`.

`handoffs` and `agent_tools` are resolved recursively through `ChildAgentGraphResolver`. The resolver rejects:

- missing child Agent definitions;
- self-reference and cycles;
- duplicate edges;
- graph depth overflow;
- Handoff-count overflow;
- Agent-as-Tool-count overflow.

Current generic execution still rejects definitions containing Handoff or Agent-as-Tool edges. STEP040 binds the graph but does not execute it.

### 2.3 Product invocation ledger

SQLite Product state now has `agent_invocation` with:

- immutable `invocation_id`;
- Product `run_id`;
- `root_invocation_id` and `parent_invocation_id`;
- kind `ROOT`, `HANDOFF`, or `AGENT_AS_TOOL`;
- state `PLANNED`, `RUNNING`, `SUCCEEDED`, `FAILED`, or `CANCELLED`;
- Agent definition identity and SHA;
- Runtime binding SHA;
- depth and stable per-Run ordinal;
- unique `state_namespace`;
- workspace access/reference;
- invocation-level token attribution;
- creation/start/completion timestamps.

One Product Run may have exactly one root invocation. Child identities require an existing parent in the same Run and exact depth continuity.

### 2.4 Existing root execution integration

The current generic Agent execution and approval-interrupted Function Tool execution create one root invocation for the existing Product Run. Terminal Product outcomes synchronize the root invocation and its accumulated token usage.

This adds no child model call and does not change canonical Product Event counts. Root invocation state is exposed separately through:

```http
GET /v1/runs/{run_id}/invocations
```

Local Admin authentication is required.

### 2.5 Workspace boundary

Language-only Agents receive:

```text
workspace_access=none
workspace_ref=null
```

`InvocationWorkspacePlanner` can derive a future isolated path from product-generated Run and invocation IDs, but STEP040 never creates the directory and grants no filesystem capability. A caller-supplied host root is rejected.

Separate host directories are not declared to be hostile-code containment. A later file-capable Agent requires a governed Sandbox/provider design.

## 3. Runtime binding impact

`AgentRuntimeBinding` now includes:

- closed child Agent graph;
- invocation policy and policy SHA;
- invocation-scope Runtime implementation SHA;
- updated execution-engine SHA.

Any change to graph, definition SHA, bounds, workspace policy, ledger behavior, or invocation implementation requires a new preflight and exact confirmation.

## 4. Deterministic acceptance

`sh_run_step040_acceptance.cmd` proves without a model or external call:

- one Product Task and Run;
- one root invocation;
- one planned Handoff child;
- one planned Agent-as-Tool child;
- exact parent/root relationships;
- unique IDs, ordinals, depths, and state namespaces;
- no workspace on language-only Agents;
- distinct future workspace previews with no materialization;
- caller-selected host root rejection;
- unresolved, self-referential, over-depth, and over-count graphs rejected;
- invocation policy and child graph Runtime-bound;
- no duplicate Product Task/Run;
- child token usage remains zero;
- no model, Tool, MCP, SDK Runner, or network call;
- unchanged References;
- acceptance cleanup completed.

## 5. Explicit non-scope

STEP040 does not implement:

- SDK Handoff execution;
- `handoff()` construction;
- Handoff history filtering;
- Agent-as-Tool nested Runner execution;
- Session;
- child Artifact transfer;
- child approval interruption;
- parallel execution;
- physical workspace creation;
- Sandbox Session;
- filesystem, Shell, network, or secret access;
- cross-process/distributed invocation leases.

## 6. Next STEP

`STEP041_NATIVE_HANDOFF_RUNTIME_V1`

STEP041 may use the ledger created here to execute exactly one language-only Handoff from a closed parent definition to a closed child definition. It must preserve `workspace_access=none`, bind the Handoff input/history policy, stream Agent changes safely, and reject loops or undeclared destinations.
