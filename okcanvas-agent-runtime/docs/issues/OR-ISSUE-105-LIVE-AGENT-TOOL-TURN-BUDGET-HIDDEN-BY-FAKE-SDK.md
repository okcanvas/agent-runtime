# OR-ISSUE-105 — Live Agent-as-Tool turn budget was hidden by the fake SDK

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Root cause

STEP087's deterministic fake Runner invoked the child Tool and returned the parent structured result inside one synthetic call. The actual bundled OpenAI Agents 0.19.0 loop increments the turn after `NextStepRunAgain` and raises `MaxTurnsExceeded` when the configured budget is exhausted.

The Root Groupware Session Agent had `max_turns=1`, although one turn is needed to invoke `groupware-read-agent` and another is needed to emit `OrganizationAssistantResult`. The child had an unnecessarily broad budget of four and no groupware-specific required Tool choice.

## Correction

- Root and child exact Live budgets are both two.
- Groupware child starts with `tool_choice=required` and `reset_tool_choice=True`.
- Existing one-edge Agent-as-Tool policy, stateless child, child-only MCP, delegated identity and read-only boundary remain unchanged.
- RuntimeInfo exposes the exact budgets without claiming Live provider success.

## Recurrence gates

- `tests/test_step087r1_live_agent_tool_turn_budget_closure.py`
- `tests/test_step087_main_assistant_stateless_groupware_subagent_delegation.py`
- `scripts/run_step087r1_acceptance.py`
- Workspace STEP004 Live E2E
