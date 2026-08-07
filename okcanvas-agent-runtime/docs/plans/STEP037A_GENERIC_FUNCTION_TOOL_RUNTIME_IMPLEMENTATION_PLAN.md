# STEP037A — Generic Function Tool Runtime V1 implementation plan

## Status

`CODE_AUDITED_IMPLEMENTATION_PLAN_COMPLETE_STEP037_WINDOWS_LIVE_RERUN_PENDING`

This is a planning addendum to the executable `STEP037_INTERACTIVE_AGENT_RUNNER_FOUNDATION`
baseline, version `2.17.0`. It does not implement STEP038 and does not change executable Runtime
behavior. STEP038 code may begin only after the STEP037 Windows acceptance gate closes.

## 1. Objective

Replace the current `local_text_metrics`-specific Function Tool path with one explicit, closed,
product-owned Function Tool Runtime that supports both:

1. one deterministic read-only Function Tool that executes without approval; and
2. the existing `local_text_metrics` Function Tool that always requires approval.

Both tools must use the installed `openai-agents==0.19.0` Function Tool and approval primitives,
share one declarative Runtime registry, participate in Runtime binding, emit the same safe Product
Tool events, and remain visible through the Interactive Runner without merging approval authority
into the Runner.

## 2. Code-derived current state

### 2.1 Existing SDK-backed approval path

The repository already proves the official SDK interruption/resume mechanism for one Tool:

- `specs/agents/local-text-metrics-agent/definition.json` declares exactly
  `tools=["local_text_metrics"]`;
- `src/okcanvas_agent_runtime/tool_approval/gateway.py` constructs an SDK Function Tool with
  `needs_approval=True`;
- `src/okcanvas_agent_runtime/tool_approval/service.py` persists encrypted `RunState`, creates the
  approval record, applies an exact operator decision, and resumes the same SDK Run;
- STEP020 through STEP023 prove approve/reject, replay, exact confirmation, Windows operator CLI,
  and one actual Tool execution after approval.

This is real Function Tool behavior, but it is not yet a generic Runtime.

### 2.2 Domain-specific branches that STEP038 must remove

The following code paths compare the literal Tool name or exact Tool tuple:

- `src/okcanvas_agent_runtime/model.py` — `governed_local_tool_name="local_text_metrics"`;
- `src/okcanvas_agent_runtime/run_submission/service.py` — exact tuple branch for
  `("local_text_metrics",)`;
- `src/okcanvas_agent_runtime/execution/runtime_binding.py` — private `_TOOL_BINDINGS` map and
  exact execution-path branch;
- `src/okcanvas_agent_runtime/tool_approval/gateway.py` — hard-coded Tool factory and prompt;
- `src/okcanvas_agent_runtime/tool_approval/service.py` — hard-coded allowlist and Tool-name checks;
- tests and deterministic fakes that assume a single literal Tool name.

The generic execution gateway currently passes `tools=[]` and accepts only allowlisted MCP Tool
lifecycle callbacks. A non-MCP Function Tool would therefore be rejected by the current lifecycle
policy even if attached to the Agent.

### 2.3 Existing declarative material

`specs/tools/local-text-metrics/policy.yaml` already records approval, filesystem, network, shell,
argument-persistence, result-persistence, and encrypted RunState policy. It lacks a complete
product-owned executable definition containing exact input/output schemas, implementation identity,
Runtime version, and SDK configuration.

## 3. Reference findings

STEP038 must follow these retained SDK implementation paths:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/tool.py::FunctionTool`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tool.py::function_tool`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tool_context.py::ToolContext`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/function_schema.py`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/util/_approvals.py`;
- `reference/upstream/openai-agents-python-0.19.0/examples/agent_patterns/human_in_the_loop.py`;
- `reference/upstream/openai-agents-python-0.19.0/examples/agent_patterns/human_in_the_loop_custom_rejection.py`;
- `reference/upstream/openai-agents-python-0.19.0/tests/test_function_tool.py`;
- `reference/upstream/openai-agents-python-0.19.0/tests/test_function_tool_decorator.py`;
- `reference/upstream/openai-agents-python-0.19.0/tests/test_tool_context.py`;
- `reference/upstream/openai-agents-python-0.19.0/tests/test_tool_identity.py`;
- `reference/upstream/openai-agents-python-0.19.0/tests/test_run_context_approvals.py`;
- `reference/upstream/openai-agents-python-0.19.0/tests/test_run_internal_approvals.py`.

Code-derived SDK contracts adopted by STEP038:

1. `FunctionTool.params_json_schema` is strict by default and must remain strict.
2. `ToolContext` is the first injected parameter and carries Tool-call identity without exposing
   arguments through Product Events.
3. `needs_approval` may be a bool or callable; V1 uses a product-resolved constant bool only.
4. SDK approval interruption uses `RunState.approve()` or `RunState.reject()` and resumes the same
   Run; STEP038 must not invent a second approval engine.
5. Function Tool output may be typed and schema-described; product code must validate and normalize
   it before returning it to the model.
6. SDK timeout, Tool Guardrail, Tool Search, namespaces, dynamic enablement, custom data, and
   programmatic callers exist but are not all P0 requirements.

## 4. Target architecture

### 4.1 Declarative Tool definition

Every executable local Function Tool must have an immutable directory:

```text
specs/tools/<tool-id>/
├─ definition.json
├─ policy.yaml
├─ input.schema.json
├─ output.schema.json
└─ TOOL.md
```

Required `definition.json` fields:

```text
schema_version
runtime_version
tool_id
sdk_kind = function_tool
factory_id
input_schema_file
output_schema_file
strict_json_schema = true
approval_mode = NEVER | ALWAYS
read_only
filesystem_access
network_access
shell_access
arguments_persisted
result_persisted_in_events
```

Executable module paths must not appear in Agent definitions and must not be dynamically imported
from specification data. `factory_id` resolves only through a closed product-owned composition.

### 4.2 Product-owned Runtime registry

Introduce a closed registry under a dedicated Runtime package, for example:

```text
src/okcanvas_agent_runtime/function_tools/
├─ __init__.py
├─ catalog.py
├─ models.py
├─ errors.py
├─ factories.py
└─ implementations.py
```

The registry resolves:

- immutable Tool definition and definition SHA;
- exact Pydantic input/output contract;
- product-owned factory callable;
- approval mode;
- read/write and capability policy;
- Runtime version;
- implementation source SHA;
- policy and schema SHAs;
- SDK Function Tool instance for one execution.

Unknown Tool IDs, unsafe paths, symlinks, schema mismatch, duplicate IDs, unknown factory IDs, and
policy/definition disagreement fail during catalog construction before preflight.

### 4.3 Minimum registered tools

#### A. Read-only Tool without approval

Provisional ID: `local_text_fingerprint`.

Purpose:

- accept only an opaque Runtime-generated `execution_id`;
- read the already-authorized protected payload through a bounded product service;
- return only SHA-256 and bounded byte/character metadata;
- perform no filesystem, network, shell, or mutation operation;
- require no approval because the governed Run request was already exactly confirmed.

This Tool exists to prove the non-approval Function Tool path. It must not expose the raw protected
text or persist Tool arguments/results in canonical Events.

#### B. Existing approval-required Tool

ID: `local_text_metrics`.

Its public behavior, exact approval phrase, encrypted RunState handling, rejection behavior, and
existing STEP020–STEP023 guarantees remain compatible. It migrates to the same registry instead of
remaining a hard-coded branch.

### 4.4 Agent definitions

Add one independent Agent definition for the read-only Tool, provisionally:

```text
specs/agents/local-text-fingerprint-agent/
```

The existing `local-text-metrics-agent` remains the approval-required example. In V1:

- every Agent may declare only registered Function Tool IDs;
- a Tool-free Agent remains valid;
- MCP and Function Tools may not be mixed in the first STEP038 slice;
- mixed approval and non-approval Function Tools in one Agent are deferred;
- approval-required V1 Agents declare exactly one approval-required Function Tool;
- Handoff and Session remain disabled.

These restrictions prevent Tool choice, multi-interruption, Session+RunState, and MCP/Function-Tool
composition from being accidentally claimed before their own acceptance.

## 5. Execution paths

### 5.1 Non-approval Function Tool path

Extend the generic SDK execution gateway to attach resolved Function Tools:

```text
Agent definition
→ FunctionToolRuntimeCatalog.resolve_many()
→ SDK Agent(tools=[...])
→ Runner.run()
→ ToolContext-bound implementation
→ safe tool.started/tool.completed Events
→ final structured output
→ Artifact/Evaluation
```

Lifecycle hooks must distinguish Tool origin explicitly:

- MCP Tool: existing allowlisted `server_id` policy;
- local Function Tool: registered `tool_id`, Runtime version, and origin policy;
- all other Tool origins: fail closed.

Canonical Event payloads persist no raw Tool arguments or results. At most they include:

```text
tool_id
runtime_version
tool_call_id_present
arguments_persisted=false
result_present
result_persisted=false
approval_required
```

### 5.2 Approval-required Function Tool path

The current approval service remains responsible for interruption storage and operator decisions,
but it resolves the Tool through the same registry:

```text
governed preflight
→ exact confirmation
→ registered approval-required Function Tool
→ SDK interruption
→ encrypted RunState + approval record
→ Approval Operator decision
→ same SDK RunState resume
→ Tool executes zero or one time
→ final Artifact
```

Remove literal `local_text_metrics` checks and replace them with exact resolved policy checks:

- Tool exists in registry;
- definition SHA matches Runtime binding;
- approval mode is `ALWAYS`;
- Agent declares exactly this Tool in V1;
- prepared interruption Tool identity matches the registered Tool;
- current registry binding still matches before resume.

The approval record continues to store only hashed arguments and bounded Tool identity metadata.

## 6. Runtime binding

Replace the private `_TOOL_BINDINGS` map with the Tool Runtime catalog. Each Tool binding entry must
include at least:

```text
tool_id
runtime_version
definition_sha256
policy_sha256
input_schema_sha256
output_schema_sha256
implementation_sha256
approval_mode
sdk_kind
```

The Agent Runtime binding additionally commits to:

- ordered Tool IDs;
- execution path selected from Tool policies rather than literal names;
- generic Function Tool gateway implementation;
- approval gateway/service implementation when any Tool requires approval.

Any Tool definition, policy, schema, implementation, approval mode, SDK option, or execution-engine
change after preflight requires a new preflight and exact confirmation.

Expected migration effect:

- STEP038 changes current Tool Runtime binding SHAs;
- existing pending Tool submissions cannot be silently reused and must be recreated;
- historical recorded Evaluation remains truthful for its recorded Runtime, but evaluating an old
  Run against the changed current Runtime fails closed under STEP036 unless historical executable
  Runtime loading is separately designed.

## 7. Product API and Interactive Runner

### 7.1 Catalog exposure

The local-admin Agent catalog response should expose bounded non-secret Tool metadata needed by the
Runner:

```text
tool_id
runtime_version
approval_mode
read_only
capability flags
```

It must not expose implementation module paths, host paths, secrets, raw schemas larger than the
bounded contract, or Tool arguments.

### 7.2 Runner behavior

The Runner must visibly distinguish:

- Tool-free Agent;
- read-only Function Tool Agent — executes after exact confirmation;
- approval-required Function Tool Agent — stops in approval-required state and links the operator
  to the separate Approval Operator surface.

The Runner must not gain approve/reject controls. Persisted Event SSE remains canonical replay;
native SDK delta streaming remains STEP039.

## 8. Exact failure contracts

STEP038 must define stable product errors for at least:

- unregistered Tool ID;
- invalid Tool definition or schema;
- Tool policy/definition mismatch;
- non-allowlisted Tool invocation observed;
- malformed Tool arguments;
- Tool implementation failure;
- Tool output contract failure;
- approval-required Tool attempted on non-approval path;
- approval interruption identity mismatch;
- Runtime binding drift before approval resume.

Error responses and Events must not copy raw arguments, Tool output, protected payload, API key, or
implementation traceback.

## 9. Deterministic acceptance design

STEP038 acceptance must include registry, positive execution, approval, rejection, and fail-closed
cases without broadening into an exhaustive matrix.

### 9.1 Registry and binding checks

- exactly two P0 Function Tools registered;
- Tool definitions, policies, input/output schemas, and implementations all bound;
- unknown Tool ID rejected before preflight;
- Tool-specific literals removed from generic gateway, submission, binding, and approval policy
  selection;
- direct executable `/reference` imports remain zero.

### 9.2 Read-only Tool success

- one governed preflight and exact confirmation;
- one SDK Runner invocation;
- one Function Tool invocation;
- no approval record;
- safe Tool started/completed Events;
- one Task/Run/Artifact;
- one compatible recorded Evaluation;
- successful protected payload deletion;
- zero filesystem/network/shell/write operation.

### 9.3 Approval Tool approve and reject

Approve branch:

- one interruption;
- one approval record;
- exact operator confirmation;
- same RunState resumed;
- Tool executes exactly once;
- one final Artifact and compatible Evaluation.

Reject branch:

- one interruption;
- Tool executes zero times;
- same RunState resumed with rejection;
- deterministic final output or exact governed rejection outcome according to the retained STEP020
  contract;
- replay creates no second execution.

### 9.4 Expected acceptance evidence

Evidence should report at minimum:

```text
registry_count
read_only_tool_invocations
approval_prepare_count
approval_execute_count
approval_reject_execute_count
runner_calls
submission/task/run/artifact/evaluation counts
safe Event types
payload retention states
runtime_binding_sha256 values
cleanup_state
```

One Windows live rerun is required because actual SDK Function Tool and RunState behavior is
material.

## 10. Implementation sequence

Implement in this order after STEP037 Windows closure:

1. add immutable Tool definitions and schemas;
2. implement Tool Runtime models/catalog and closed factories;
3. make Agent definition validation resolve Tool IDs through the catalog;
4. replace `_TOOL_BINDINGS` with registry-backed Runtime binding;
5. add generic non-approval Function Tool execution to the SDK gateway;
6. migrate approval gateway/service from literal Tool checks to registry policy;
7. expose bounded Tool capability metadata through catalog API and Runner;
8. add unit tests for registry, schema, identity, Event safety, and drift;
9. add STEP038 deterministic acceptance;
10. run full regression, previous approval acceptance, Reference integrity, package extraction, and
    Windows launcher checks;
11. package a Canonical ZIP whose HANDOFF records the exact Windows gate for STEP038.

## 11. Files expected to change

Likely new files:

```text
src/okcanvas_agent_runtime/function_tools/*
specs/tools/local-text-fingerprint/*
specs/tools/local-text-metrics/definition.json
specs/tools/local-text-metrics/input.schema.json
specs/tools/local-text-metrics/output.schema.json
specs/agents/local-text-fingerprint-agent/*
tests/test_function_tool_runtime_catalog.py
tests/test_generic_function_tool_execution.py
scripts/run_step038_acceptance.py
sh_run_step038_acceptance.cmd
docs/plans/STEP038_GENERIC_FUNCTION_TOOL_RUNTIME_V1.md
docs/evidence/STEP038_ACCEPTANCE.json
```

Likely modified files:

```text
src/okcanvas_agent_runtime/agent_definitions/catalog.py
src/okcanvas_agent_runtime/run_submission/service.py
src/okcanvas_agent_runtime/execution/openai_gateway.py
src/okcanvas_agent_runtime/execution/runtime_binding.py
src/okcanvas_agent_runtime/tool_approval/gateway.py
src/okcanvas_agent_runtime/tool_approval/service.py
src/okcanvas_agent_runtime/control_api/app.py
src/okcanvas_agent_runtime/interactive_runner/assets/*
AGENTS.md
HANDOFF.md
PLANS.md
docs/plans/ROADMAP.md
```

Exact files must be re-confirmed from call paths before editing; this list is not authority to make
unrelated changes.

## 12. Explicit non-scope

STEP038 does not implement:

- Shell, Apply Patch, Web Search, File Search, Code Interpreter, Computer Use, or hosted Tools;
- dynamic Tool Search or deferred Tool loading;
- programmatic Tool calling;
- Tool input/output Guardrails — STEP044;
- SDK native streaming — STEP039;
- Handoff or Agent-as-Tool;
- Session or Memory;
- multiple approval interruptions in one Run;
- mixed MCP and Function Tool execution in one Agent;
- arbitrary plugin import;
- model-selected implementation, policy, approval mode, host path, environment, or capability;
- raw Tool argument/result persistence;
- general distributed Tool execution.

## 13. STEP038 completion gate

STEP038 may be declared implemented only when:

1. the literal-tool branches listed in section 2.2 are removed from generic policy selection;
2. two Tools resolve through one closed registry;
3. non-approval and approval-required paths both execute through installed SDK primitives;
4. approve and reject behavior retain the existing exactly-once guarantees;
5. Runtime binding covers complete Tool executable identity;
6. Runner displays both Tool modes without approval authority;
7. deterministic acceptance and all previous approval/Runtime regressions pass;
8. the Canonical ZIP contains complete plan, Evidence, Windows commands, and next-step handoff.
