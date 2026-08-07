# OR-ISSUE-058 — STEP081D Windows-live promotion flags remained false in current-state tests

## Symptom

The STEP082B full Python regression failed three tests in files 200–219. RuntimeInfo correctly promoted three proven STEP081D Windows-live capabilities to `True`, while current-state tests still required `False`.

## Code-confirmed root cause

STEP081D's real 80/80 live run proved the architecture constitution, Windows npm subprocess portability, and architecture validator process-isolation paths. STEP082B promoted these RuntimeInfo fields, but the older current-baseline assertions were not migrated with the Product state.

## Impact

No runtime behavior failed. The tests contradicted user-provided accepted evidence and blocked the full regression.

## Correction

Only the three current-state assertions were changed to `True`. Historical STEP081A/STEP081B failure summaries and immutable evidence remain unchanged.

## Recurrence gate

- `tests/test_step080a_architecture_constitution_and_compliance_gates.py`;
- `tests/test_step081a_windows_npm_command_resolution_and_subprocess_portability.py`;
- `tests/test_step081b_live_architecture_validator_isolation.py`;
- full STEP082B Python regression.
