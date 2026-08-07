# OR-ISSUE-101 — Delegated identity forwarding preceded gateway kwargs

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP087_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_DELEGATION`

## Problem

The first implementation inserted delegated identity into `gateway_kwargs` before that dictionary was created, causing `UnboundLocalError` before gateway execution.

## Correction

Removed the premature reference and added the identity only at the normal gateway kwargs construction point.

## Recurrence gate

STEP087 execution service regression and end-to-end submission execution.
