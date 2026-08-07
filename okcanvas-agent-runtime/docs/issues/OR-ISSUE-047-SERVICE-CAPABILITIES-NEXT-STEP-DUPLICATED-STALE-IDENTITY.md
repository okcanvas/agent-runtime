# OR-ISSUE-047 — Service capabilities retained duplicated stale STEP identity

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_VALIDATION_PENDING_WINDOWS_RERUN`

## Exact symptom

The STEP081B full Python regression failed three authenticated Service API tests. `RuntimeInfo.next_selected_step` returned the STEP081B pending Gate, while `/v1/service/capabilities` still returned:

```text
UNSELECTED_PENDING_STEP081A_WINDOWS_LIVE_ACCEPTANCE
```

Affected regressions:

- `tests/test_step069_multi_user_service_client_contract.py`
- `tests/test_step070_product_owned_skill_foundation.py`
- `tests/test_step074_product_owned_docker_sandbox_provider_lifecycle.py`

## Code-confirmed root cause

`okcanvas_agent_runtime/application/service/use_cases.py` owned a second literal `next_selected_step` value instead of deriving the current Product identity from the canonical Runtime baseline. Updating `RuntimeInfo` alone therefore left the authenticated capabilities projection stale.

## Impact

The Product package and RuntimeInfo identified STEP081B, but authenticated external clients observed STEP081A as the pending promotion Gate. This violated the single-current-step contract and caused three real API regressions.

## Fix

The Service capabilities projection is aligned to `UNSELECTED_PENDING_STEP081B_WINDOWS_LIVE_ACCEPTANCE`. Current-step assertions remain executable at the authenticated route boundary.

## Automated recurrence gates

- `tests/test_step069_multi_user_service_client_contract.py`
- `tests/test_step070_product_owned_skill_foundation.py`
- `tests/test_step074_product_owned_docker_sandbox_provider_lifecycle.py`
- STEP081B full Python regression
- STEP081B live Service capabilities check
