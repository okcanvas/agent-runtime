# OR-ISSUE-102 — Deterministic gateway did not commit Session history

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP087_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_DELEGATION`

## Problem

The deterministic service gateway returned successful outputs but did not append user/assistant items to the fake SDK Session. Runtime Session integrity validation correctly rejected the later state with `SessionIntegrityError`.

## Correction

Made the deterministic gateway use the same SDK Session item contract and commit two items per successful turn.

## Recurrence gate

STEP087 Session service test and Workspace two-turn E2E requiring 2 turns / 4 items.
