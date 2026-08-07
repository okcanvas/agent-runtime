# OR-ISSUE-080 — Step085 Local Evidence Not Excluded From Product Inventory

## Status

```text
FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_COMPLIANCE_ACCEPTED_WINDOWS_PENDING
```

## STEP

```text
STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION
```

## Repeatable symptom

STEP085 local checkpoint paths were not initially registered as machine-local exclusions.

## Root cause

The new delegated multi-MCP boundary crossed an older single-MCP/current-state contract that was not yet versioned for the new identity or transport mode.

## Fix

Add step085-local to inventory exclusions, .gitignore and an automated recurrence test.

## Evidence and recurrence gate

test_step085_local_evidence_is_excluded_from_product_inventory and Fresh forbidden-entry Gate.

## Safety result

No secret value, uncontrolled write authority, external endpoint or durable automation capability is enabled by this correction.
