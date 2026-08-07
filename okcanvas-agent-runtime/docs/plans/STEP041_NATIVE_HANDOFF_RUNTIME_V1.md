# STEP041 — Native Handoff Runtime V1

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Executable baseline: `okcanvas-agent-runtime 2.21.0`.

STEP040 Sub-Agent Invocation Scope Foundation is Windows live accepted. STEP041 is the first actual child-Agent execution and must reuse the STEP040 Product invocation ledger rather than introducing another child identity, state, usage, or workspace mechanism.

## 1. Code-confirmed problem

The installed OpenAI Agents SDK provides native `handoff()` and changes the current Agent inside one Runner execution. It does not create an OKCanvas Product invocation, partition cumulative usage between the previous and new Agent, allocate or forbid a filesystem workspace, or persist a safe canonical Handoff Event.

Before STEP041, definitions could declare Handoff edges and STEP040 could create planned child identities, but generic execution rejected every Handoff-bearing Agent. A direct SDK connection would therefore have produced an observable Agent change without a product-owned child lifecycle.

## 2. Implemented vertical slice

STEP041 executes exactly one language-only Handoff:

```text
handoff-triage-agent
└─ native SDK handoff()
   └─ handoff-specialist-agent
```

The entire flow stays inside one governed Submission, Task, and Product Run.

### 2.1 Immutable Handoff policy

`specs/runtime/native-handoff-policy.json` fixes:

- one Handoff per Product Run;
- maximum depth one;
- `REMOVE_ALL_TOOLS` input filtering;
- `nest_handoff_history=false`;
- no Handoff input payload;
- same parent/child output contract;
- `workspace_access=none` for both Agents.

The policy and implementation are included in the confirmation-bound Runtime binding.

### 2.2 Closed parent and child definitions

The parent definition declares exactly one child in `handoffs`. The child is terminal and language-only:

- no Handoff edge;
- no Agent-as-Tool edge;
- no Function Tool;
- no MCP;
- no Session;
- no filesystem workspace.

The Runtime rejects missing, undeclared, self-referential, cyclic, mixed-capability, over-depth, or over-count destinations before Product execution.

### 2.3 Installed SDK construction

Product code constructs native SDK Handoff through installed `openai-agents==0.19.0`:

- `handoff(child_agent, ...)`;
- deterministic Tool name;
- `agents.extensions.handoff_filters.remove_all_tools`;
- `nest_handoff_history=False`.

Executable code never imports `/reference`.

### 2.4 Invocation lifecycle

At execution start:

```text
ROOT invocation = RUNNING
```

At the single SDK Handoff callback:

1. verify the SDK `from_agent` and `to_agent` against the immutable graph;
2. capture cumulative parent usage;
3. terminalize ROOT as `SUCCEEDED` with that usage;
4. create and start one `HANDOFF` child invocation;
5. emit one safe canonical `agent.handoff` Event;
6. continue SDK execution as the child Agent.

At final success:

- Product Run stores total cumulative usage;
- child usage is `total - parent`;
- child invocation becomes `SUCCEEDED`;
- one final Artifact is registered under the Product Run;
- recorded Evaluation verifies the root Runtime binding and Artifact.

On a failure after transfer, only the active child invocation is terminalized by Product Run synchronization; the already-successful parent invocation is not rewritten.

### 2.5 Usage partition

V1 assumes one sequential Handoff and cumulative SDK usage. It calculates:

```text
parent usage = cumulative usage observed at Handoff
child usage = final cumulative Run usage - parent usage
Product Run usage = final cumulative Run usage
```

Negative or inconsistent deltas fail closed.

### 2.6 Event and stream boundary

Canonical `agent.handoff` persists only:

- from/to Agent IDs;
- from/to invocation IDs;
- child definition and Runtime binding identity;
- input-filter mode;
- history/input-payload persistence flags;
- workspace state.

It does not persist Handoff arguments, raw history, Tool records, prompts, instructions, or model output.

Native ephemeral streaming may expose the safe child Agent update and output text delta. Raw Handoff output/history objects remain dropped by the STEP039 adapter.

### 2.7 Workspace boundary

Both parent and child have:

```text
workspace_access=none
workspace_ref=null
```

No physical folder, Sandbox Session, filesystem Tool, Shell, network capability, mount, or inherited writable parent root is created.

## 3. APIs and visible behavior

Existing APIs are reused:

- governed preflight and exact confirmation;
- `GET /v1/runs/{run_id}/invocations` for root/child lifecycle;
- `GET /v1/runs/{run_id}/events` for canonical Handoff evidence;
- `GET /v1/runs/{run_id}/sdk-stream` for ephemeral safe Agent change;
- verified Artifact API;
- recorded Evaluation API.

No second Handoff-specific Product Run API or ledger is introduced.

## 4. Deterministic acceptance

`sh_run_step041_acceptance.cmd` proves:

- executable Handoff preflight;
- native SDK Handoff constructed exactly once;
- `Runner.run_streamed()` once and `Runner.run()` zero times;
- one Product Submission, Task, and Run;
- exactly two invocations: ROOT and HANDOFF;
- both invocations succeed with exact relationship, depth, ordinal, and namespace;
- parent usage `12/4/16`;
- child usage `18/6/24`;
- Product Run total usage `30/10/40`;
- exactly one canonical safe Handoff Event;
- `REMOVE_ALL_TOOLS`, no nested history, no Handoff input payload;
- no raw history in Product DB or native stream;
- safe child Agent update in native stream;
- no parent or child workspace;
- one verified Artifact and one PASSED recorded Evaluation;
- successful protected payload deletion;
- final Product counts `1/1/1/2/14/1/1` for Task/Run/Submission/Invocation/Event/Artifact/Evaluation;
- no raw request or keys in Product DB;
- unchanged References and completed cleanup.

## 5. Explicit non-scope

STEP041 does not implement:

- multiple or chained Handoffs;
- Handoff depth above one;
- Handoff input payload objects;
- nested Handoff history;
- Handoff combined with Function Tool, MCP, Agent-as-Tool, Session, or approval;
- file-capable child Agents;
- physical workspace or Sandbox;
- child-specific Artifact ownership or Artifact transfer;
- child-specific recorded Evaluation;
- parallel Agent execution;
- process-loss resume in the middle of an SDK Handoff;
- distributed invocation lease;
- dynamic/model-selected destinations.

## 6. Next STEP

`STEP042_AGENT_AS_TOOL_RUNTIME_V1`

STEP042 must reuse the same invocation ledger and workspace constitution to run one declared language-only specialist through `Agent.as_tool()`. It must preserve parent control after the nested call, create one `AGENT_AS_TOOL` child invocation, attribute nested usage without creating a second Product Run, expose safe nested-Agent stream metadata, and keep Session, Handoff mixing, approval, and filesystem capability disabled.
