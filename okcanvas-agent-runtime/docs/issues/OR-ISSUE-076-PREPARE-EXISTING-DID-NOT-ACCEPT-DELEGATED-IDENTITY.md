# OR-ISSUE-076 — Prepare Existing Did Not Accept Delegated Identity

## Status

```text
FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_COMPLIANCE_ACCEPTED_WINDOWS_PENDING
```

## STEP

```text
STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION
```

## Repeatable symptom

Execution restoration supplied delegated identity but PreparedGenericExecution.prepare_existing initially had no matching parameter.

## Root cause

The new delegated multi-MCP boundary crossed an older single-MCP/current-state contract that was not yet versioned for the new identity or transport mode.

## Fix

Extend the preparation contract and preserve identity through guarded execution.

## Evidence and recurrence gate

STEP085 focused execution tests and full regression.

## Safety result

No secret value, uncontrolled write authority, external endpoint or durable automation capability is enabled by this correction.
