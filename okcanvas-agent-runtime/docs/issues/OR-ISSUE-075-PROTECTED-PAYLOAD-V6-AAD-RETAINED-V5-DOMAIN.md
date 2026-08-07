# OR-ISSUE-075 — Protected Payload V6 Aad Retained V5 Domain

## Status

```text
FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_COMPLIANCE_ACCEPTED_WINDOWS_PENDING
```

## STEP

```text
STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION
```

## Repeatable symptom

Protected payload content advanced to V6 for delegated identity while AAD validation initially remained on the V5 domain.

## Root cause

The new delegated multi-MCP boundary crossed an older single-MCP/current-state contract that was not yet versioned for the new identity or transport mode.

## Fix

Align V6 AAD with delegation_id and retain V3/V4/V5 backward reads.

## Evidence and recurrence gate

tests/test_step085_multi_mcp_and_delegated_identity_foundation.py protected round-trip; full STEP085 regression.

## Safety result

No secret value, uncontrolled write authority, external endpoint or durable automation capability is enabled by this correction.
