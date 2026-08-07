# WORKSPACE-ISSUE-034 — STEP008R2 Live MCP ToolOutput protocol and SEARCH Tool choice

## Observed Windows evidence

- Deterministic STEP008R2: 25/25 PASSED.
- Live STEP008R2: 19/29 FAILED.
- All four prompts reached OpenAI, Child Agent, MCP Tool start and completion.
- All four then failed in Product-owned normalization with `NESTED_OUTPUT_NORMALIZATION_FAILED / ValueError`.
- `과장들 목록` called `resolve_organization_context` instead of the admitted `search_organization_context`.

## Root cause

The pinned SDK returns MCP results as `ToolOutputTextDict(type="text", text=<JSON>)` (or a list), while the STEP008R2 adapter expected the JSON payload itself. Separately, `tool_choice=required` required a Tool but did not bind the admitted operation.

## Recurrence prevention

- Contract tests use the exact bundled SDK ToolOutput text wrapper, not `SimpleNamespace(output=json.dumps(...))`.
- Tests prove named `RESOLVE` and `SEARCH` Tool choices from immutable request hints.
- Normalization errors expose only bounded categories, never raw payloads.
- Live acceptance requires the exact resolve/resolve/resolve/search sequence.
