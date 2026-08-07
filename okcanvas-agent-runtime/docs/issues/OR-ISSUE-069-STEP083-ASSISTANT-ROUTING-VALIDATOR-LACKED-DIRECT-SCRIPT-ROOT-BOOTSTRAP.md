# OR-ISSUE-069 — STEP083 Assistant routing validator lacked direct-script root bootstrap

## Symptom

Direct execution of `python scripts/validate_step083_assistant_routing.py` failed with `ModuleNotFoundError: No module named 'okcanvas_agent_runtime'`, although pytest and integrated acceptance had passed.

## Code-confirmed root cause

The validator imported Product packages before resolving and inserting the repository root into `sys.path`. Importing it from a test or another repository-root-aware script masked the defect.

## Impact

Canonical evidence generation could not run from the direct script entrypoint and therefore could not produce `STEP083_ASSISTANT_ROUTING_VALIDATION.json`.

## Correction

The validator now inserts its repository root before Product imports, matching the direct-script contract used by other current validators.

## Recurrence gate

- direct execution of `scripts/validate_step083_assistant_routing.py`;
- STEP083 portability validation;
- STEP083 integrated and Fresh acceptance.
