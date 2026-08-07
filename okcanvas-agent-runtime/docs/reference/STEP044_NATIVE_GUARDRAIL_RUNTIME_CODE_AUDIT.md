# STEP044 — Native Guardrail Runtime code audit

## Audited immutable Reference

Primary files inspected:

- `reference/upstream/openai-agents-python-0.19.0/examples/agent_patterns/input_guardrails.py`
- `reference/upstream/openai-agents-python-0.19.0/examples/agent_patterns/output_guardrails.py`
- `reference/upstream/openai-agents-python-0.19.0/examples/basic/tool_guardrails.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/guardrail.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tool_guardrails.py`
- Guardrail exceptions and corresponding tests under the same immutable upstream tree.

Executable Runtime imports only the installed `agents==0.19.0` package.

## Upstream findings

### Agent input Guardrail

The SDK decorator creates an `InputGuardrail` with `run_in_parallel` control. The official example demonstrates a tripwire exception. For a product guarantee that rejected input causes no model call, STEP044 requires `run_in_parallel=false`.

### Agent output Guardrail

Output Guardrails receive the final Agent output. A tripwire raises after the output exists but before the caller accepts successful completion. Product code therefore must catch the exception before Artifact registration and must preserve incurred usage without persisting the output.

### Tool Guardrails

Tool Guardrails are attached directly to a `FunctionTool` through `tool_input_guardrails` and `tool_output_guardrails`. Native `raise_exception` behavior distinguishes:

- input tripwire before implementation;
- output tripwire after implementation.

This ordering is materially different and must be demonstrated through exact Tool execution counts.

### SDK exception gap

Native exceptions identify the Guardrail and may carry Run usage, but they do not:

- terminalize Product Task/Run/Submission/invocation state;
- map to stable product error codes;
- apply protected-payload retention;
- prevent Product Artifact registration by themselves;
- create safe canonical Event evidence;
- verify immutable Agent/Tool/Guardrail Runtime binding.

These remain product-owned responsibilities.

## Pre-STEP044 product gaps

Before STEP044 the Runtime had:

- Pydantic structured-output validation;
- Function Tool input/output JSON schemas;
- Product policy and exact confirmation;
- safe Tool Events;

but no installed-SDK input/output/Tool Guardrail construction, no tripwire exception mapping, no Guardrail catalog, no Runtime binding for Guardrails, and no canonical tripwire Evidence.

## Adopt / adapt / reject

### Adopt

- installed SDK `input_guardrail`, `output_guardrail`;
- installed SDK `tool_input_guardrail`, `tool_output_guardrail`;
- `GuardrailFunctionOutput` and `ToolGuardrailFunctionOutput.raise_exception`;
- four native tripwire exception classes;
- `run_in_parallel=false` for input-before-model proof.

### Adapt

- immutable product specifications under `specs/guardrails`;
- closed implementation IDs instead of arbitrary callables from definitions;
- safe Event metadata and exact Product error codes;
- Product usage, invocation, retention, Artifact and Evaluation handling;
- Guardrail definitions and implementation in Runtime binding;
- existing `FunctionToolRuntimeCatalog` for Tool target resolution.

### Reject for V1

- dynamically imported Guardrail callables;
- model-generated Guardrail definitions;
- raw `output_info` persistence;
- raw guarded content or SDK exception persistence;
- parallel input Guardrail execution;
- mixed Session/child/MCP/approval/workspace capability graph;
- Guardrail override, retry, fallback or post-tripwire Artifact.

## Code changes

### New package

`src/okcanvas_agent_runtime/guardrails/` contains:

- immutable models and kinds;
- path-safe closed catalog;
- SDK Agent Guardrail builders;
- Tool Guardrail attachment;
- explicit errors.

### Agent catalog

Agent definitions may declare a unique `guardrails` list. The catalog resolves Guardrail capabilities, checks Tool target closure, enforces one-per-kind V1 limits and rejects mixed unsupported capabilities.

### Runtime binding

`AgentRuntimeBinding` now contains `guardrails` and `guardrail_runtime_sha256`. Guardrail definitions, implementation and execution path are confirmation-bound.

### Gateway

`OpenAIGenericAgentGateway`:

- builds native Agent and Tool Guardrails;
- catches all four SDK exception types;
- validates exception Guardrail identity against the immutable resolved graph;
- emits one safe `guardrail.tripped` Event;
- raises one exact `GenericExecutionErrorCode` with available usage/trace evidence;
- never persists `output_info`, guarded input/output or raw SDK errors.

### Product execution

The execution service validates the `native-guardrail-execution-v1` binding, includes safe Guardrail identity in `agent.definition.resolved`, persists incurred usage on failure, terminalizes the ROOT invocation and creates no rejected Artifact.

## Security assessment

The marker-based fixture policies are deliberately deterministic acceptance fixtures, not a claim of production semantic moderation. The security property being proven is the Runtime boundary: immutable policy identity, native SDK interception timing, exact failure mapping, data minimization and Product terminalization.

Guardrail marker plaintext is not included in public binding/catalog output; only a SHA is bound. However protected Session/input content remains sensitive in its own storage lifecycle and failed payloads are retained under existing investigation policy.

## Acceptance evidence interpretation

The five-case acceptance proves:

- input tripwire before model because only four of five cases call the model;
- output tripwire after model because that case consumes model usage yet creates no Artifact;
- Tool-input tripwire before implementation because execution count is zero;
- Tool-output tripwire after implementation because execution count is one;
- Pydantic validation remains separate because the clean structured result validates and Guardrail codes are distinct;
- canonical Product evidence contains no guarded raw content.

## Remaining risks and deferred work

- real-model semantic Guardrails require separately designed models/prompts/evaluation;
- parallel Agent input Guardrails need cancellation/race analysis;
- multiple Guardrails of one kind need deterministic ordering and complete Evidence semantics;
- Session, Handoff, Agent-as-Tool and approval composition need dedicated combined acceptance;
- Tool output may already have caused external effects before an output Guardrail trips; V1 uses a read-only capability-free Tool and does not claim rollback;
- distributed execution and process-loss recovery around tripwire timing remain unclaimed.

## Next planning implication

The P0 primitives required for the basic Runtime skeleton now exist independently. STEP045 should integrate them visibly rather than add another isolated abstraction. It must preserve all existing authority and isolation boundaries while demonstrating the capability matrix through the Interactive Runner.
