# OR-ISSUE-083 — STEP085 Zero Credential Reference Assertion Blocked Read-only Vertical

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`
FIX_IMPLEMENTED_FOCUSED_REGRESSION_ACCEPTED_FULL_VALIDATION_PENDING
```

## Symptom

The first STEP086 focused regression failed `test_default_product_access_catalog_has_no_credential_values` after the Product Configuration Pack added the Groupware `credential_ref` metadata required by the selected read-only vertical.

The failing assertion required:

```text
MCPAccessCatalog.secret_references == {}
```

although the STEP085 security contract was that credential **values** must not be stored or exposed, not that future Product Configuration Packs may never declare a credential reference.

## Root cause

A historical STEP085 regression encoded the temporary default count (`0`) as a permanent security invariant. This coupled the preserved Multi-MCP foundation to the exact STEP085 catalog contents and rejected a legitimate additive read-only configuration in STEP086.

## Fix

The historical regression now verifies the durable invariant:

- every declared credential reference has an identifier and environment-variable locator;
- public metadata count matches the catalog;
- credential values remain unexposed;
- no secret value is persisted in Product definitions, bindings, events, artifacts, or protected payload evidence.

STEP086 separately verifies that the default Groupware endpoint remains `.invalid`, the referenced environment secret is absent, and readiness is `NOT_CONFIGURED`.

## Recurrence gate

`tests/test_step085_multi_mcp_and_delegated_identity_foundation.py::test_default_product_access_catalog_has_no_credential_values` and `tests/test_step086_groupware_read_only_vertical.py`.
