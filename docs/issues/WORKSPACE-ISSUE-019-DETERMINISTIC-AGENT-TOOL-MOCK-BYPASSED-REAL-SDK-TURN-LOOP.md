# WORKSPACE-ISSUE-019 — Deterministic Agent-as-Tool mock bypassed the real SDK turn loop

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Root cause

The STEP003 deterministic gateway and Runtime STEP087 fake SDK proved the composition graph but did not execute the bundled OpenAI Agents run loop. The Root definition retained `max_turns=1`. In the actual SDK, the first Root turn invokes the child Tool and a second Root model turn is needed to produce `OrganizationAssistantResult`. The child similarly needs one MCP Tool turn and one final-output turn.

With the prior budget a real Live request would raise `MaxTurnsExceeded` after successful child invocation. The deterministic mock returned the parent output directly and therefore could not expose this defect.

## Correction

- Root `organization-assistant-session-agent.max_turns = 2`.
- Child `groupware-read-agent.max_turns = 2`.
- Groupware child Tool choice is required for its first model turn and reset after the Tool call.
- Child Session remains disabled, MCP remains child-owned, call count remains one, and write access remains disabled.
- Runtime STEP087R1 verifies the bundled SDK turn-loop source and exact live budgets.

## Recurrence gates

- `okcanvas-agent-runtime/tests/test_step087r1_live_agent_tool_turn_budget_closure.py`
- Generic Gateway fake-SDK construction assertions
- Runtime STEP087R1 deterministic acceptance
- Workspace STEP004 deterministic and Windows Live acceptance
