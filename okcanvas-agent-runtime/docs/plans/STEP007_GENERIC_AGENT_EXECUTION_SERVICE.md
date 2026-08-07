# STEP007_GENERIC_AGENT_EXECUTION_SERVICE

## Objective

Connect one immutable, tool-free declarative Agent definition to the official OpenAI Agents SDK Runner and the STEP005 Task/Run/Event/Artifact product state without duplicating SDK execution behavior.

## Reference code inspected

The implementation first used `reference/CODE_MAP.md` and `reference/MANIFEST.json`, then inspected:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/agent.py`
  - **ADOPT** the SDK `Agent` fields for instructions, model, Tools, Handoffs and structured `output_type`.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run.py`
  - **ADOPT** `Runner.run`, `RunConfig`, explicit `max_turns`, `group_id`, trace metadata and `session=None`.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/lifecycle.py`
  - **ADAPT** `RunHooks` lifecycle callbacks into canonical product Run events without persisting raw prompts, requests or model output.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/result.py`
  - **ADOPT** `final_output_as(...)` and `last_response_id` rather than parsing SDK internals.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/usage.py`
  - **ADAPT** aggregate usage into durable Run token columns and completion Event metadata.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tracing/create.py`
  - **ADOPT** SDK-generated trace IDs and `RunConfig` trace linkage with sensitive trace data disabled.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/memory/session.py`
  - **DEFER** SDK Session. Product Task/Run state remains separate and the first generic execution explicitly passes `session=None`.
- `reference/upstream/openai-agents-streaming-api/src/api/utils/agent_router.py`
  - **REJECT for this STEP** direct REST/SSE adaptation. Durable canonical Events must be the source for a later interface.

## Scope

- immutable `specs/agents/<id>/definition.json` resolver;
- combined definition/instructions/output-schema SHA-256;
- schema registry check against the runtime Pydantic contract;
- zero-Tool, zero-Handoff, session-disabled policy;
- one persisted Task and Run per accepted invocation;
- SDK lifecycle normalization into append-only canonical Events;
- trace and token usage linkage to the Run record;
- structured final output as a hash-verified Artifact;
- CLI definition inspection and generic execution;
- deterministic local acceptance plus Windows live-acceptance harness.

## Non-scope

- multiple Agents or Handoffs;
- Function Tools, hosted Tools or Codex;
- SDK Session or persisted RunState;
- MCP;
- HTTP, SSE or UI;
- external workspace access;
- raw request persistence;
- cost calculation or pricing policy.

## Canonical lifecycle

```text
run.created
run.started
agent.definition.resolved
agent.started
model.started
model.completed
agent.completed
artifact.created
run.completed
```

On failure after Run start:

```text
agent.failed
run.failed
```

## Security and evidence

- explicit live-call confirmation remains mandatory;
- the raw request is represented in product state only by SHA-256;
- API keys, instructions, prompts and final model text are not copied into Run Events;
- final structured output is stored in an external Artifact file and registered by SHA-256;
- trace IDs and aggregate usage are product references, not a replacement for the SDK trace;
- the output JSON schema must exactly match the registered runtime Pydantic contract before a Task is created.

## Acceptance criteria

1. the coding Agent definition resolves with an immutable combined SHA;
2. path traversal, symbolic files, unknown fields and schema drift fail before execution;
3. no unconfirmed request creates Task or Run records;
4. a deterministic gateway creates one successful Task and Run;
5. lifecycle Events have monotonic sequence and the canonical order;
6. trace ID and usage are linked to the Run;
7. the final output Artifact verifies by SHA and byte length;
8. raw request and API-key sentinels are absent from SQLite;
9. SDK contract test proves zero Tools, zero Handoffs, `session=None`, hooks and sensitive-trace exclusion;
10. all four reference trees remain unchanged;
11. full regression and packaged-ZIP verification pass.

## Live acceptance

`sh_run_step007_live_acceptance.cmd` performs one actual model invocation and requires:

- successful Task and Run;
- non-empty trace ID and token usage;
- normalized SDK lifecycle Events;
- verified final-output Artifact;
- raw request and API key absent from SQLite;
- all reference trees unchanged.

Until that Windows run passes, STEP007 remains `IMPLEMENTED_NOT_LIVE_ACCEPTED`.
