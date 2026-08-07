# STEP075F — Exact Evidence Output Completeness and Bounded Repair

## Identity

- Step: `STEP075F_EXACT_EVIDENCE_OUTPUT_COMPLETENESS_AND_BOUNDED_REPAIR`
- Version: `2.55.6`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Trigger

STEP075E Windows live execution proved the complete read-only Sandbox runtime path: two `gpt-4.1` model calls, one completed Sandbox Tool call, deterministic tar materialization, exactly one immutable project file selected, selected-file hashes verified, cleanup completed, orphan count zero, final Artifact creation and successful Run completion.

The acceptance harness still returned 32/33 because the schema-valid final answer omitted the exact expression `max(0, forecast + SAFETY_STOCK - on_hand)` and `SAFETY_STOCK = 12`, and incorrectly listed evidence-backed `src/inventory.py` under `unverified`.

## Selected scope

1. Strengthen immutable Sandbox Agent instructions for exact formula, signature, assignment, constant value, identifier, operator and literal requests.
2. Recover exactly one bounded in-memory `SandboxProjectReadonlyInspectOutput` from the completed SDK run.
3. Derive exact requested Python function expressions and referenced uppercase constant assignments from bounded Tool evidence.
4. Validate `CodingAgentResult` before Product Artifact registration.
5. If incomplete, invoke at most one separate Product-owned correction model call.
6. Give the correction Agent no Tool, filesystem, Shell, network, MCP, Handoff or write capability.
7. Never re-run the Sandbox Tool during answer repair.
8. Aggregate repair usage into final Run usage.
9. Persist only bounded completeness/repair lifecycle metadata; never persist the raw request, bounded Tool evidence or draft answer in those Events.
10. Fail closed with `ANSWER_COMPLETENESS_FAILED` if the bounded repair remains incomplete.
11. Distinguish runtime failure from `RUNTIME_ACCEPTED_ANSWER_COMPLETENESS_FAILED` in live evidence.
12. Record the repeatable failure as OR-ISSUE-006.

## Explicit non-scope

- no Docker, tmpfs, tar, snapshot or hash-domain change;
- no second Sandbox Tool execution;
- no Shell, Apply Patch, arbitrary executable or dependency installation;
- no network, MCP, Handoff, Agent-as-Tool or Skill capability;
- no raw evidence/draft persistence;
- no unlimited retry or repair loop;
- no STEP076 selection.

## Acceptance gates

- the exact STEP075E draft is deterministically classified incomplete;
- required fragments include the exact function name, complete expression and referenced constant assignment;
- evidence-backed files cannot remain in `unverified`;
- an already-complete output performs zero repair calls;
- an incomplete output performs exactly one no-tool repair call;
- Sandbox Tool execution remains exactly one;
- repair usage is included in total usage;
- completeness/repair Events contain only bounded metadata;
- repair failure is stable `ANSWER_COMPLETENESS_FAILED`;
- focused, historical, full Python, Node, Reference and packaging validations pass;
- Windows live rerun succeeds before STEP076 selection.
