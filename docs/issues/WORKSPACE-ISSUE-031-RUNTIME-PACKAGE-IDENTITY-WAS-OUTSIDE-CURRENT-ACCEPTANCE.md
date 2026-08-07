# WORKSPACE-ISSUE-031 — Runtime package identity was outside current acceptance

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

Runtime `STEP088R1`, discovered during Workspace STEP008 implementation

## Evidence

`scripts/package_source.py` still declared:

```text
DEFAULT_OUTPUT → STEP087R1 filename
PACKAGE_STEP   → STEP087R2
```

while the current Runtime was STEP088R1. The retained package identity test failed, but STEP088R1 deterministic acceptance still reported 24/24 because that test was not in its focused regression list.

## Root cause

Current package identity was distributed across mutable literals, and the current acceptance gate did not directly assert both `PACKAGE_STEP` and `DEFAULT_OUTPUT.name`.

## Correction

Runtime STEP089 aligns both package identities and adds `package_identity_exact` directly to the STEP089 acceptance payload. The stale retained test is part of the focused regression.

## Recurrence gate

Every promoted Runtime STEP must fail its own acceptance unless:

```text
PACKAGE_STEP == CURRENT_STEP
DEFAULT_OUTPUT.name == current canonical archive name
```
