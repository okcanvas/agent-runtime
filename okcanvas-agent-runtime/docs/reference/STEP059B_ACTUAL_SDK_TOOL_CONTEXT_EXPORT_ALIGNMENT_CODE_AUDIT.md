# STEP059B Code and Immutable SDK Audit

## Immutable SDK evidence

- `src/agents/__init__.py` exports `function_tool` but has no `ToolContext` import or `__all__` entry.
- `src/agents/tool_context.py` defines `class ToolContext(RunContextWrapper[TContext])`.
- SDK examples, docs, and tests consistently use `from agents.tool_context import ToolContext`.
- `src/agents/function_schema.py` recognizes either `RunContextWrapper` or this exact
  `agents.tool_context.ToolContext` type as the first callable context parameter.

## Product defect

`src/okcanvas_agent_runtime/function_tools/factories.py` imported both names from top-level
`agents`. Installed SDK 0.19.0 therefore raised `ImportError` before Function Tool creation.

## Test defect

Product fake SDKs incorrectly assigned `fake_agents.ToolContext`, creating an export that the real
SDK does not provide. STEP059B moves fake context classes into `sys.modules["agents.tool_context"]`
and leaves top-level `agents.ToolContext` absent.

## Corrected contract

- top-level: `from agents import function_tool`;
- submodule: `from agents.tool_context import ToolContext`;
- output contract remains `output_type=runtime.output_model` only;
- all three Product Function Tools share the corrected factory.

## Remaining live gate

Deterministic and source-reference checks cannot substitute for the user Windows environment.
The package remains pending until `sh_run_step059b_acceptance.cmd` and a real governed
`project-readonly-coding-agent` run both succeed.
