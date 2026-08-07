# OR-ISSUE-026 — Historical packaging assertions retained the STEP080A candidate identity

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

The STEP041 native-handoff, STEP042 agent-as-tool, and STEP072B local-evidence regressions required `scripts/package_source.py` to contain the STEP080A ZIP filename even though the packaging implementation had correctly advanced to the STEP081 candidate. Both tests failed after all feature-specific assertions passed.

## Code-confirmed root cause

Historical feature tests combined their own behavioral contract with a mutable current-release packaging filename. Updating the Product release identity therefore invalidated unrelated older feature tests.

## Impact

A correct STEP081 package identity could not pass the complete historical regression suite. Reintroducing the STEP080A filename would package the wrong release and make the ZIP handoff ambiguous.

## Fix

The historical tests now verify the current STEP081 deterministic ZIP identity while retaining all native-handoff and agent-as-tool feature assertions.

## Detailed evidence

The 140–159 Python regression chunk passes after the assertions are aligned with the current packaging contract.

## Recurrence-prevention gate

`tests/test_step041_native_handoff_runtime_baseline.py` and `tests/test_step042_agent_as_tool_runtime_baseline.py` require the canonical STEP081 ZIP filename emitted by `scripts/package_source.py`. The STEP081 deterministic acceptance also verifies package identity before finalization.
