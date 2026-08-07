# STEP059A — Actual SDK Function Tool Output Contract Alignment

## Baseline

- Project: `okcanvas-agent-runtime`
- Version: `2.39.1`
- STEP: `STEP059A_ACTUAL_SDK_FUNCTION_TOOL_OUTPUT_CONTRACT_ALIGNMENT`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_ACTUAL_SDK_RERUN_PENDING`

## Why this correction exists

The complete STEP059 deterministic acceptance passed, but the first real Windows OpenAI execution of
`project-readonly-coding-agent` failed after `agent.definition.resolved` and before `agent.started`,
`model.started`, or `tool.started`.

Code audit found that Product `build_sdk_function_tool()` passed both `output_type` and
`output_json_schema`. The immutable `openai-agents-python-0.19.0` SDK explicitly declares those
arguments mutually exclusive and raises `UserError` during FunctionTool construction.

The fake SDK used by existing tests did not enforce that contract, so the deterministic gate was
insufficient.

## Correction

All Product Function Tools now bind exactly one SDK output contract:

```python
output_type=runtime.output_model
```

`output_json_schema` is not passed. The SDK derives the strict output schema from the Pydantic model
and retains typed output validation through its `TypeAdapter`.

This applies to all registered Product Function Tools:

- `local_text_fingerprint`;
- `local_text_metrics`;
- `project_readonly_inspect`.

## Preserved boundaries

- Tool inputs remain opaque execution IDs;
- protected user text remains Product supplied;
- raw Tool arguments/results remain absent from persisted Events;
- project inspection remains bounded and read-only;
- relative path/line evidence remains unchanged;
- no write, Shell, Git, network, MCP, Session, Handoff, Agent-as-Tool, Guardrail, or Sandbox authority is added.

## Acceptance

### Deterministic gate

A contract-exact fake SDK rejects dual output binding. All three Product Tools must construct with
`output_type` present and `output_json_schema` absent. Project evidence must remain repository-relative.

### Windows actual-SDK gate

`sh_run_step059a_acceptance.cmd` imports the installed `openai-agents==0.19.0` package and constructs
all three Product Function Tools. Each must expose an SDK-generated output schema and output type
adapter without raising `UserError`.

After that gate passes, manually rerun the real `project-readonly-coding-agent` question. A successful
run must show `agent.started`, `model.started`, `tool.started`, `tool.completed`, Artifact creation,
and terminal success.

STEP060 remains blocked until the actual-SDK gate and real project Tool run are reported successful.
