# STEP059B Actual SDK ToolContext Export Alignment

## State

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_ACTUAL_SDK_RERUN_PENDING`

## Confirmed defect

The first STEP059A Windows actual-SDK acceptance failed before any Tool construction. Product code used:

```python
from agents import ToolContext, function_tool
```

Immutable `openai-agents-python-0.19.0` proves that `function_tool` is exported from `agents`, while
`ToolContext` is defined in `agents.tool_context` and is not re-exported by `agents.__init__`.
SDK examples, documentation, and tests import it from the submodule.

## Change

Use the exact SDK import split:

```python
from agents import function_tool
from agents.tool_context import ToolContext
```

Fake SDKs must mirror this export structure and must not add a top-level `ToolContext` attribute.

## Acceptance

`sh_run_step059b_acceptance.cmd` uses installed `openai-agents==0.19.0` to:

- import `ToolContext` from `agents.tool_context`;
- confirm it is absent from the top-level package;
- construct all three Product Function Tools;
- confirm output schema and output adapter binding;
- construct an actual SDK `Agent` containing `project_readonly_inspect` without a model call.

## Exclusions

No STEP060 feature work, Tool authority expansion, write, Shell, Git, network, MCP, Guardrail,
Session, Handoff, Agent-as-Tool, or Sandbox change is included.
