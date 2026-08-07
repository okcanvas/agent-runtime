# OR-ISSUE-103 — Groupware policy was eagerly loaded for unrelated projects

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP087_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_DELEGATION`

## Problem

Runtime binding and Submission loaded the Groupware Session policy for every temporary project, breaking unrelated fixtures that intentionally lacked Groupware specs.

## Correction

Load and validate the policy only when the exact Main Assistant definition and Groupware route require it.

## Recurrence gate

Unrelated temporary-project regressions plus STEP087 exact-root tests.
