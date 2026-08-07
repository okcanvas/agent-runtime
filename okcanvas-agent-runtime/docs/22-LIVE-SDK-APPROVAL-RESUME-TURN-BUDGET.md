# Live SDK approval resume turn budget

## Confirmed defect

The STEP020 live prepare path called the Agents SDK with `max_turns=1`. The first model turn produced the approval interruption. SDK `RunState` serializes both `current_turn` and `max_turns`, and `Runner.run(agent, state)` restores the saved budget. Approval or rejection then requires a second model turn to process the Tool result or rejection and finalize the run. The persisted one-turn budget therefore caused `MaxTurnsExceeded` during the decision process.

## Fix

`OpenAILocalToolApprovalGateway` now uses a bounded two-turn budget:

1. turn 1: request `local_text_metrics` and interrupt for approval;
2. turn 2: process approval/rejection and finalize.

The budget is not unbounded and no Tool scope is broadened.

## Acceptance diagnostics

STEP020 child processes now always write a result envelope on Python exceptions. Parent acceptance code records redacted stdout/stderr and validates the child return code before reading its result. A child failure is reported as the original error instead of being overwritten by a missing `decision-result.json` error.

Raw API keys and local authority keys are redacted from child-process Evidence.
