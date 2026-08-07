# OR-ISSUE-006 — STEP075E exact evidence answer completeness

## Status

`FIX_IMPLEMENTED_WINDOWS_REPAIR_FAILED_SUPERSEDED_BY_OR_ISSUE_007`

## Exact symptom

STEP075E Windows live execution completed the Product Run successfully with two `gpt-4.1` model calls and one completed read-only Sandbox Tool call. Docker workspace materialization, selected-file hash verification, internal metadata exclusion, cleanup, orphan reconciliation, security restrictions, Artifact creation and payload deletion all passed. The acceptance harness nevertheless returned 32/33 because `formula_observed` was false.

The structured answer named `calculate_reorder`, cited `src/inventory.py lines 1-4`, and described `max(0, ...)`, but omitted the exact evidence-backed expression `max(0, forecast + SAFETY_STOCK - on_hand)` and the assignment `SAFETY_STOCK = 12`. It also placed the evidence-backed `src/inventory.py` path in `unverified`.

## Code-confirmed gap

The Sandbox Agent instructions required an exact answer but did not define a Product-owned post-output completeness gate. A schema-valid `CodingAgentResult` therefore became the final Artifact even when exact identifiers, operators, literals and constant assignments requested by the user were replaced by ellipsis or generic paraphrase.

## Impact

Infrastructure success and evidence integrity could be incorrectly reported as an overall acceptance failure, while a schema-valid but incomplete answer could still be registered as the successful Product Artifact. Evidence-backed paths could also be mislabeled as unverified.

## Fix

1. Strengthen the immutable Sandbox Agent instructions for exact formula, signature, assignment, identifier, operator, literal and constant-value requests.
2. Extract the single in-memory `SandboxProjectReadonlyInspectOutput` from the SDK result without persisting raw Tool output.
3. Derive exact requested Python function expressions and referenced constant assignments from bounded Tool evidence.
4. Validate the structured draft before Artifact registration.
5. When incomplete, invoke one Product-owned correction Agent with no tools, filesystem, Shell, network, MCP, Handoff or write capability.
6. Do not re-run the Sandbox Tool during repair.
7. Validate the repaired output again and fail with `ANSWER_COMPLETENESS_FAILED` if it remains incomplete.
8. Persist only bounded check/repair lifecycle metadata, never raw request, evidence or draft.
9. Distinguish `RUNTIME_ACCEPTED_ANSWER_COMPLETENESS_FAILED` from infrastructure failure in live evidence.

## Automated recurrence prevention

- `tests/test_step075f_sandbox_answer_completeness_and_bounded_repair.py`
- exact STEP075E failure draft regression
- exact formula and constant-assignment completeness regression
- evidence-backed path exclusion from `unverified`
- one repair model call maximum
- repair Agent has zero tools/MCP/Handoff/workspace capability
- Tool execution count remains one
- aggregate usage includes repair usage
- STEP075F deterministic acceptance
- STEP075F Windows live acceptance


## STEP075F Windows result

The bounded correction model call executed but the repaired answer still failed the deterministic completeness validator. OR-ISSUE-007 owns the replacement with Product-owned deterministic evidence completion.
