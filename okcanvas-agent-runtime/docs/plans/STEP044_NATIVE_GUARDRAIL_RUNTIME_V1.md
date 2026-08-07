# STEP044 — Native Guardrail Runtime V1

## Status

- Executable baseline: `okcanvas-agent-runtime 2.24.0`
- STEP: `STEP044_NATIVE_GUARDRAIL_RUNTIME_V1`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`
- Previous Windows closure: STEP043 SQLite Session Runtime V1 passed all 29 checks.

## Purpose

STEP044 adds the installed OpenAI Agents SDK Guardrail tripwire boundary as a first-class, product-governed Runtime capability. It proves four distinct interception points without conflating them with Pydantic output-contract validation:

1. Agent input Guardrail before model execution;
2. Agent output Guardrail after structured output but before Artifact registration;
3. Function Tool input Guardrail before Tool implementation;
4. Function Tool output Guardrail after Tool implementation but before the result can be accepted.

The first slice is Session-disabled, child-free, MCP-free, approval-free, language/file-workspace free, and uses only the existing read-only `local_text_fingerprint` Tool for Tool Guardrail proof.

## Code-audited SDK boundary

The installed SDK and immutable Reference establish that:

- `input_guardrail(..., run_in_parallel=False)` may trip before the first model call;
- output Guardrails inspect the final Agent output and raise `OutputGuardrailTripwireTriggered` before normal completion;
- Tool input/output Guardrails attach to a `FunctionTool` and may return `ToolGuardrailFunctionOutput.raise_exception(...)`;
- Tool-input tripwire occurs before the Tool implementation;
- Tool-output tripwire occurs after the Tool implementation;
- the SDK exceptions carry Guardrail identity and may carry accumulated Run usage, but do not provide Product Task/Run terminalization, retention, safe canonical Events, Runtime binding, or Artifact policy.

Executable code imports only the installed `agents` package. `/reference` remains immutable and import-forbidden.

## Product-owned closed Guardrail catalog

Guardrails are immutable specifications under:

```text
specs/guardrails/<guardrail-id>/definition.json
```

V1 contains exactly four definitions:

| Guardrail | Kind | Target | Behavior |
|---|---|---|---|
| `block-input-marker` | INPUT | Agent input | `RAISE_EXCEPTION` |
| `block-output-marker` | OUTPUT | Agent output | `RAISE_EXCEPTION` |
| `deny-local-text-tool-input` | TOOL_INPUT | `local_text_fingerprint` | `RAISE_EXCEPTION` |
| `deny-local-text-tool-output` | TOOL_OUTPUT | `local_text_fingerprint` | `RAISE_EXCEPTION` |

The catalog rejects symbolic directories/files, path escape, malformed keys, unknown implementation IDs, unsupported behavior, duplicate IDs, invalid kind/target combinations, parallel V1 input checks, and Tool Guardrails whose target Tool is absent from the Agent definition.

Markers remain definition data but only `marker_sha256` enters the public Runtime-binding dictionary. Public catalog responses do not expose the marker text.

## Agent definitions

STEP044 adds:

- `guardrail-language-agent` — input and output Guardrails, no Tool;
- `guardrail-tool-input-agent` — read-only `local_text_fingerprint` plus Tool-input Guardrail;
- `guardrail-tool-output-agent` — the same Tool plus Tool-output Guardrail.

All three require:

```text
session_mode=disabled
handoffs=[]
agent_tools=[]
mcp_servers=[]
workspace_access=none
```

A Guardrail Agent may have at most one Guardrail of each V1 kind. Guardrails cannot be mixed with Handoff, Agent-as-Tool, MCP, Session, approval Tool or physical workspace in STEP044.

## Native execution lifecycle

### Clean path

```text
input Guardrail passes
→ model executes
→ output Guardrail passes
→ Product Run succeeds
→ Artifact registered
→ recorded Evaluation may run
```

### Input tripwire

```text
input Guardrail trips
→ model calls=0 for that case
→ guardrail.tripped
→ Run/ROOT invocation FAILED
→ no Artifact
```

### Output tripwire

```text
model executes and produces structured output
→ output Guardrail trips
→ guardrail.tripped
→ Run/ROOT invocation FAILED
→ no Artifact
```

### Tool-input tripwire

```text
model selects declared Tool
→ Tool-input Guardrail trips
→ Tool executions=0
→ Run/ROOT invocation FAILED
→ no Artifact
```

### Tool-output tripwire

```text
model selects declared Tool
→ Tool-input checks pass
→ Tool executes exactly once
→ Tool-output Guardrail trips
→ Run/ROOT invocation FAILED
→ no Artifact
```

## Exact Product error codes

Each native exception maps to one exact Product code:

- `INPUT_GUARDRAIL_TRIPPED`
- `OUTPUT_GUARDRAIL_TRIPPED`
- `TOOL_INPUT_GUARDRAIL_TRIPPED`
- `TOOL_OUTPUT_GUARDRAIL_TRIPPED`

These codes are distinct from output-contract validation failures. A schema-invalid final output remains an output-contract error, not a Guardrail tripwire.

## Canonical Event safety

Each rejected Run records exactly one `guardrail.tripped` Event containing only:

- `guardrail_id`;
- `guardrail_kind`;
- optional declared `tool_id`;
- `behavior`;
- `tripwire_triggered=true`;
- `guarded_content_persisted=false`;
- `output_info_persisted=false`;
- `raw_sdk_error_persisted=false`.

The Event must not contain input/output text, Tool arguments/results, SDK `output_info`, prompts, instructions, reasoning, call IDs, API keys, or raw exception objects.

## Runtime binding

Exact confirmation binds:

- each Guardrail definition SHA;
- Guardrail kind, target Tool, behavior and parallel policy;
- Guardrail implementation SHA;
- aggregate `guardrail_runtime_sha256`;
- Agent definition and output-contract identity;
- Function Tool Runtime when a Tool Guardrail is used;
- generic Gateway, execution service, output and streaming implementation.

The execution path is `native-guardrail-execution-v1`. A changed definition, implementation, target Tool, policy, Agent graph or execution engine requires a new preflight and exact confirmation.

## Failure, Artifact and retention policy

- A tripwire terminalizes the same Product Task, Run, Submission and ROOT invocation as failed.
- No rejected Run may register an Artifact or Evaluation.
- Usage already incurred before a tripwire is persisted when the SDK exposes it.
- The clean success payload is deleted immediately.
- All four failed protected payloads are retained for the existing failure-investigation window.
- STEP044 does not retry, resume, replace, or reinterpret a tripwire failure.

## Deterministic acceptance

`run_step044_acceptance.py` creates five separately governed runs:

1. clean input/output Guardrail pass;
2. Agent-input tripwire;
3. Agent-output tripwire;
4. Tool-input tripwire;
5. Tool-output tripwire.

It proves all 23 checks with:

- `Runner.run_streamed=5`, `Runner.run=0`;
- total model calls `4`;
- Tool executions: input-guarded `0`, output-guarded `1`;
- Guardrail checks executed: INPUT `3`, OUTPUT `2`, TOOL_INPUT `1`, TOOL_OUTPUT `1`;
- one safe tripwire Event per rejected Run;
- clean Artifact verified and recorded Evaluation `PASSED`;
- rejected Artifact count `0`;
- five terminal ROOT invocations and no workspace;
- final Task/Run/Submission/Invocation/Event/Artifact/Evaluation `5/5/5/5/48/1/1`;
- success payload deleted, four failed payloads retained;
- no raw sentinels or API key in Product/Evaluation DB;
- unchanged References and cleanup `COMPLETED`.

## Explicit non-scope

STEP044 does not implement:

- Guardrail mixed with Session, Handoff, Agent-as-Tool, MCP, approval or workspace;
- multiple Guardrails of the same kind in one Agent;
- non-exception Tool Guardrail behaviors;
- dynamic Guardrail code, model-generated policy or arbitrary plugin import;
- model-based policy judge Guardrails;
- Guardrail output persistence or operator override;
- retry, fallback, approval, resume, or Artifact creation after tripwire;
- cross-process Guardrail state or distributed execution;
- Guardrail-specific UI editor.

## Windows gate

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step044_acceptance.cmd
```

All 23 checks, exact Runner/model/Tool counts, four exact failure codes, Product counts, Artifact policy, payload retention, Reference integrity and cleanup must pass before STEP045 executable work begins.

## Next STEP

`STEP045_INTEGRATED_WALKING_SKELETON_ACCEPTANCE`

STEP045 must not add another isolated primitive first. It must integrate the already implemented P0 capabilities through the governed Interactive Runner and prove the basic Runtime skeleton end to end: Tool-free, Function Tool, approval, MCP, native streaming, Handoff, Agent-as-Tool, Session, Guardrail, Artifact and recorded Evaluation.
