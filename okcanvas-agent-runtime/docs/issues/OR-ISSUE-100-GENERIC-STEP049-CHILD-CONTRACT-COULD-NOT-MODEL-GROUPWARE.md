# OR-ISSUE-100 — Generic STEP049 child contract could not model Groupware

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP087_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_DELEGATION`

## Problem

The retained STEP049 Agent-as-Tool contract requires a language-only child with the same output schema as the root. Groupware requires a child-owned MCP server and `GroupwareReadResult`, distinct from the root `OrganizationAssistantResult`.

## Correction

Preserved STEP049 unchanged and added a separate exact Groupware Session delegation contract.

## Recurrence gate

STEP049 retained regression plus STEP087 fake-SDK construction assertions.
