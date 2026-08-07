# OR-ISSUE-085 — Historical Remote MCP Catalog Exact List Blocked Groupware Vertical

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`
FIX_IMPLEMENTED_CHUNK_REGRESSION_RERUN_PENDING
```

## Symptom

The STEP086 chunked full regression failed the preserved STEP066 Remote MCP test because it required the complete active MCP catalog to equal only:

```text
[reference-catalog]
```

STEP086 legitimately adds the allowlisted `groupware-read` V3 read-only server definition while retaining the STEP066 V2 example as a non-enabled template.

## Root cause

The historical test combined two different invariants:

1. the STEP066 `organization-search` V2 example must remain a reserved, non-allowlisted template;
2. no later Product step may add any MCP server.

Only the first invariant belongs to STEP066. The second was an unintended exact-list freeze that prevented additive Product evolution.

## Fix

The regression now verifies that:

- `reference-catalog` remains active;
- the `organization-search` example remains absent from the allowlist;
- the new `groupware-read` server is V3 and read-only.

The exact STEP086 Groupware Tool allowlist, delegated identity, endpoint and credential readiness contracts are owned by the STEP086 test suite.

## Recurrence gate

`tests/test_step066_remote_mcp_streamable_http_mvp_foundation_baseline.py::test_remote_template_remains_non_enabled_and_reserved` and `tests/test_step086_groupware_read_only_vertical.py`.
