# WORKSPACE_STEP007R1_ORGANIZATION_CONTEXT_BOUNDED_RESPONSE_AND_LIVE_FAILURE_DIAGNOSTIC_CLOSURE

## Goal

Close the proven STEP007 Windows Live failure without increasing the 32,000-character Runtime MCP result budget.

## Scope

1. Bound `resolve_organization_context` to top-score detailed candidates.
2. Bound `search_organization_context` to twenty compact summaries.
3. Retain `get_organization_entity` as the detailed relation read.
4. Propagate response-shape and truncation metadata through the real Connector.
5. Persist only safe MCP result-limit diagnostics in Runtime events.
6. Reuse the existing STEP007 full-process Live harness with the same two prompts.

## Non-goals

- No production DB implementation.
- No mutation MCP Tool.
- No increase to `max_result_chars=32000`.
- No replacement of the STEP084 local catalog.
- No claim of Windows Live acceptance until rerun.
