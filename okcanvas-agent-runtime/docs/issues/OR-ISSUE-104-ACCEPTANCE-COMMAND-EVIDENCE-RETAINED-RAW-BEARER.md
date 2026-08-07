# OR-ISSUE-104 — Acceptance command evidence retained raw bearer

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP087_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_DELEGATION`

## Problem

The first Workspace E2E successfully protected stdout, stderr and Runtime artifacts but persisted the raw Product CLI `--bearer` argv value in command metadata.

## Correction

Mask the value immediately after every `--bearer` argument before evidence serialization.

## Recurrence gate

Workspace STEP003 evidence redaction check and secret scan.
