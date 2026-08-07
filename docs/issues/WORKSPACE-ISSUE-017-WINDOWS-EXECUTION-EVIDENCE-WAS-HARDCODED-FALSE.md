# WORKSPACE-ISSUE-017 — Windows execution evidence was hardcoded false

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Actual failure

The real Windows STEP003R1 payload reported:

```json
"windows_step003r1_executed": false
```

although the payload itself was produced by that Windows execution.

## Root cause

The limitation field was a packaging-time constant intended to prevent unsupported claims. It was not derived from the execution platform and therefore became false evidence after a real Windows run.

## Correction

STEP003R2 records:

```text
execution_platform
windows_step003r2_executed
windows_step003r2_accepted
```

`executed` is derived from `os.name == "nt"`. `accepted` is true only when the same Windows run ends with aggregate `state: PASSED`.

## Recurrence gates

- Platform must be recorded in every aggregate payload.
- Windows execution and Windows acceptance must be separate fields.
- A failed Windows run must report executed=true and accepted=false.
- A non-Windows run must never claim Windows execution or acceptance.
