# WORKSPACE-ISSUE-011 — Integration catalog lagged accepted Runtime flow

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Evidence

The STEP002R1 Product CLI had already passed its real Windows Service API execution, but `specs/workspace/integration-contracts.json` still declared `service-cli-runtime` as `implemented: false`. It also had no contract for the STEP003 Main Assistant Session to invoke `groupware-read-agent` as an Agent tool.

## Root cause

The executable projects advanced while the Workspace integration catalog remained at the earlier foundation state.

## Correction

- Marked `service-cli-runtime` implemented.
- Added the exact `runtime-main-assistant-groupware-subagent` `AGENT_AS_TOOL` contract.
- Bound the root, child, child MCP owner, stateless child session, one-call limit and read-only policy.

## Recurrence gate

Workspace structure tests and STEP003 acceptance require the exact catalog, Runtime version, root/child IDs and integration contracts.
