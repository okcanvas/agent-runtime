# OR-ISSUE-099 — Session Groupware routing and delegated identity were blocked

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP087_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_DELEGATION`

## Problem

The Product router explicitly returned `groupware-session-composition-disabled` for a Session plus Groupware request, and execution derived delegated MCP identity only from MCP servers owned by the root Agent. A child-owned MCP binding could therefore never execute through the Main Assistant Session.

## Correction

Added an exact Groupware Session delegation policy, selected the required stateless child only for the matching route, and forwarded delegated identity independently of root MCP ownership.

## Recurrence gate

STEP087 routing, submission, binding and execution tests plus Workspace STEP003 full E2E.
