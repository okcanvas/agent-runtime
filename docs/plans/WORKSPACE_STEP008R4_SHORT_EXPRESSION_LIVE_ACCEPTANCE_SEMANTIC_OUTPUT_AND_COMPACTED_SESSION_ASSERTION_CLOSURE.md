# WORKSPACE_STEP008R4_SHORT_EXPRESSION_LIVE_ACCEPTANCE_SEMANTIC_OUTPUT_AND_COMPACTED_SESSION_ASSERTION_CLOSURE

```text
Version: 0.8.4
Scope: Workspace Live acceptance harness only
Product Runtime: STEP090R1 / 2.70.1 unchanged
```

## Proven input

The actual Windows STEP008R3 run completed all four Product Runs successfully with the exact Tool sequence `resolve / resolve / resolve / search`. The formal harness returned 27/29 because two predicates contradicted valid runtime behavior.

## Corrections

1. Empty-list output is validated from structured evidence: `ANSWERED`, `search_organization_context`, `candidate_count=0`, no citations, no unverified entries. No Korean wording substring is required.
2. Session continuity is validated from four `session.turn.completed` events for one Session with `turn_count` values `1,2,3,4`. The current Session `item_count` is not constrained after legitimate compaction.
3. Product Runtime, Router, Agent definitions, Skills, MCP Tools and normalizer are unchanged.

## Acceptance

- Local/Fresh deterministic gates must pass.
- Windows deterministic and Windows Live launchers must be rerun from a clean R4 extraction.
- Formal promotion requires Live 29/29 with all four Runs SUCCEEDED.

## Local result

```text
Workspace tests: 99/99 PASSED
Runtime STEP090R1: 25/25 PASSED
Workspace STEP008R4: 25/25 PASSED
Manifest drift: 0
```
