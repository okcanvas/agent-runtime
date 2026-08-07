# STEP059A Code and Immutable SDK Audit

## Evidence that triggered the audit

The user's real Windows run of `project-readonly-coding-agent` produced only:

1. `run.created`;
2. `run.started`;
3. `agent.definition.resolved`;
4. `agent.failed`;
5. `run.failed`;
6. `payload.retention.applied`.

No Agent, model, or Tool lifecycle start event occurred. The separate STEP059 fixture acceptance still
passed 16/16, proving that its fake SDK did not cover the failed real-SDK phase.

## Exact code path

Product path:

`src/okcanvas_agent_runtime/function_tools/factories.py`

The original decorator supplied both:

- `output_type=runtime.output_model`;
- `output_json_schema=runtime.output_model.model_json_schema()`.

Immutable SDK path:

`reference/upstream/openai-agents-python-0.19.0/src/agents/tool.py`

`_resolve_function_tool_output()` checks both arguments and raises:

`UserError("output_type and output_json_schema cannot both be provided.")`

This occurs while the FunctionTool is built, before `Runner` can invoke Agent/LLM lifecycle hooks.
That ordering exactly matches the reported Event sequence.

## Corrected design

Product passes `output_type` only. The SDK's `_build_function_tool_output_type()` derives the output
schema and adapter from the same Pydantic model. This avoids duplicate authorities while preserving
strict schema generation and runtime output validation.

The correction is in the shared Tool factory, so all three registered Function Tools are aligned.

## Test-gap closure

The new fake SDK contract raises immediately when both arguments are supplied. Tests assert that all
Product Tools bind one output contract only. The Windows acceptance additionally imports the actual
installed SDK and constructs all three Tools without making an OpenAI network request.

## Non-claims

The deterministic gate cannot replace the Windows actual-SDK gate. It proves Product source and the
immutable contract are aligned, while the Windows gate proves the installed package behaves as
expected. A separate real OpenAI Tool run is still required to close STEP059A live acceptance.
