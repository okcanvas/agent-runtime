# OR-ISSUE-108 — MCP ToolOutput text wrapper and short-list named Tool choice

## Windows evidence

STEP008R2 deterministic passed 25/25, but STEP008R2 Live OpenAI failed 19/29. All four short prompts completed one MCP call and then failed in the Product-owned normalizer with `NESTED_OUTPUT_NORMALIZATION_FAILED / ValueError`. The list prompt `과장들 목록` invoked `resolve_organization_context` instead of `search_organization_context`.

## Proven root causes

The pinned `openai-agents==0.19.0` implementation returns MCP content as a model-visible `ToolOutputTextDict(type="text", text=<JSON>)`, or a list of ToolOutput dictionaries, when `use_structured_content=False`. STEP090 tests used a simplified direct JSON string and the adapter did not unwrap the real protocol shape.

The Child Agent used `tool_choice="required"`. That requires some Tool but does not enforce the admitted `preferred_operation=SEARCH` contract.

## Correction

- Decode the exact SDK text ToolOutput dictionary/list protocol before reading the allowlisted Tool result.
- Keep exactly-one allowlisted Tool result and stable-ID ambiguity checks fail-closed.
- Map only immutable admitted `RESOLVE` and `SEARCH` request hints to named Child function Tool choices.
- Treat the hint only as an operation contract, never as Entity evidence.
- Record bounded normalization categories without raw model output, Tool arguments, Tool results, or raw errors.

## Recurrence gates

- Exact SDK-shaped text dictionary and list tests.
- Bundled upstream source contract test for MCP ToolOutput conversion.
- Named RESOLVE/SEARCH Tool-choice tests and gateway binding test.
- Live acceptance exact sequence: resolve / resolve / resolve / search.
- Runtime full suite exact partition coverage.
