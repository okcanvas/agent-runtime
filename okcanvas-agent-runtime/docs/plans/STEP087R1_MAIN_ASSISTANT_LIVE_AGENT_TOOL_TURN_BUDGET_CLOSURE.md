# STEP087R1_MAIN_ASSISTANT_LIVE_AGENT_TOOL_TURN_BUDGET_CLOSURE

Version `2.67.1`

## Problem

The deterministic STEP087 fake Runner bypassed the real OpenAI Agents loop. Root `max_turns=1` could invoke the Agent Tool but could not perform the second parent model turn required for the final `OrganizationAssistantResult`.

## Exact correction

```text
Root max_turns    2
Child max_turns   2
Child Tool choice required on first turn
Child reset_tool_choice true
Child Session     disabled
Child MCP         groupware-read only
Maximum child calls per Root turn 1
Write enabled     false
```

## Deterministic gate

```cmd
sh_run_step087r1_acceptance.cmd
```

Live OpenAI success is intentionally not claimed by this Runtime-only deterministic correction. Workspace STEP004 owns the full Windows Live E2E.
