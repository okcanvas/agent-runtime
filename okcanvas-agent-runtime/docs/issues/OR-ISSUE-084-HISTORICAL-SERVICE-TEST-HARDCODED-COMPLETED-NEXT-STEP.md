# OR-ISSUE-084 — Historical Service Test Hardcoded Completed Next Step

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`
FIX_IMPLEMENTED_FOCUSED_REGRESSION_ACCEPTED_FULL_VALIDATION_PENDING
```

## Symptom

The first STEP086 focused regression failed the authenticated Service capability contract because a STEP069 historical test still required:

```text
next_selected_step == STEP086_GROUPWARE_READ_ONLY_VERTICAL
```

After STEP086 became the current implemented step, the canonical RuntimeInfo correctly no longer reported it as the next step.

## Root cause

The Product endpoint had already been corrected in OR-ISSUE-053 to derive `next_selected_step` from `RuntimeInfo`, but one historical regression independently owned the same mutable literal. The duplicated test expectation recreated the stale-current-state failure class during the next additive step.

## Fix

The historical Service test now compares the endpoint projection against the canonical `RuntimeInfo().next_selected_step` value instead of owning a specific successor identity. STEP086 records `UNSELECTED_PENDING_USER_SELECTION` because the user supplied no STEP087 scope and guessing is prohibited.

The same stale successor literal was also found in the preserved STEP080A architecture-constitution RuntimeInfo regression and was corrected to require the current unselected state.

## Recurrence gate

`tests/test_step069_multi_user_service_client_contract.py::test_service_capability_and_principal_contract`, STEP086 RuntimeInfo validation, and authenticated `/v1/service/capabilities` coverage.
