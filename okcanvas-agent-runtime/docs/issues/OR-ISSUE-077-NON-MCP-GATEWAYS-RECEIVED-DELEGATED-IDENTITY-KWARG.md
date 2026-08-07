# OR-ISSUE-077 — Non Mcp Gateways Received Delegated Identity Kwarg

## Status

```text
FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_COMPLIANCE_ACCEPTED_WINDOWS_PENDING
```

## STEP

```text
STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION
```

## Repeatable symptom

Delegated identity was initially forwarded to all gateways, breaking existing non-MCP fake gateway contracts.

## Root cause

The new delegated multi-MCP boundary crossed an older single-MCP/current-state contract that was not yet versioned for the new identity or transport mode.

## Fix

Pass delegated identity only when the prepared Agent actually declares MCP servers.

## Evidence and recurrence gate

existing gateway regressions plus STEP085 full regression.

## Safety result

No secret value, uncontrolled write authority, external endpoint or durable automation capability is enabled by this correction.
