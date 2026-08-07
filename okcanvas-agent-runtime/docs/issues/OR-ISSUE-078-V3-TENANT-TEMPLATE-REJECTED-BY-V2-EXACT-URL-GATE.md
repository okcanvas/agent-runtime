# OR-ISSUE-078 — V3 Tenant Template Rejected By V2 Exact Url Gate

## Status

```text
FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_COMPLIANCE_ACCEPTED_WINDOWS_PENDING
```

## STEP

```text
STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION
```

## Repeatable symptom

The OpenAI MCP factory initially required definition.url and rejected valid V3 url_template definitions.

## Root cause

The new delegated multi-MCP boundary crossed an older single-MCP/current-state contract that was not yet versioned for the new identity or transport mode.

## Fix

Accept an exact V2 URL or a validated V3 tenant template, never an unbound endpoint.

## Evidence and recurrence gate

STEP085 two-server factory/runtime-binding tests and validator 22/22.

## Safety result

No secret value, uncontrolled write authority, external endpoint or durable automation capability is enabled by this correction.
