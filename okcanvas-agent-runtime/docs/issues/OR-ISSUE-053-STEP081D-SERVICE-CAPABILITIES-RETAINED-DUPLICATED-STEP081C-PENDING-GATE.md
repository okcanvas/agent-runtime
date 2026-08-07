# OR-ISSUE-053 — STEP081D Service capabilities retained a duplicated STEP081C pending Gate

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_VALIDATION_PENDING_WINDOWS_RERUN`

## Observed failure

After STEP081D updated the canonical `RuntimeInfo.next_selected_step`, ten historical and authenticated Service capability regressions showed that `ServiceUseCases.capabilities()` still returned the literal `UNSELECTED_PENDING_STEP081C_WINDOWS_LIVE_ACCEPTANCE`.

## Cause

The Service response owned a second hardcoded next-step value instead of reading the canonical RuntimeInfo contract. This repeated the duplicate identity class already recorded by OR-ISSUE-047.

## Corrective implementation

`ServiceUseCases.capabilities()` now uses `RuntimeInfo().next_selected_step`. No Service-local STEP pending string remains.

## Recurrence gates

- authenticated STEP069/070/074/076/080 Service capability tests,
- repository search for stale pending-Gate literals,
- STEP081D full and Fresh Python regression.
