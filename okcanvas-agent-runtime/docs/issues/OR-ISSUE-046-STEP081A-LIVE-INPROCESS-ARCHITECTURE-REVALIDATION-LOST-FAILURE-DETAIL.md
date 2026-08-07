# OR-ISSUE-046 — STEP081A live in-process architecture revalidation lost failure detail

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_VALIDATION_PENDING_WINDOWS_RERUN`

## Exact symptom

The real Windows command `sh_run_step081a_live_acceptance` completed the Product runtime path but ended:

```text
state: FAILED
passed_checks: 75
total_checks: 77
terminal_status: SUCCEEDED
model_calls: 2
tool_calls: 1
sandbox cleanup_state: COMPLETED
sandbox orphan_count: 0
```

The only false checks were:

```text
step081_static_architecture_gate_complete
step081_transport_topology_runtime_bound
```

The emitted summary did not contain the architecture validator payload, its failed check names, route inventory, child-process exit state, stdout, or stderr. The exact Windows sub-check that made the transport topology false therefore could not be recovered from the acceptance artifact.

## Code-confirmed cause

`run_step081_live_acceptance.py` imported and called `validate_step081_architecture()` inside the already-populated live Acceptance process. The deterministic STEP081A Acceptance runs the same validator in a separate process and had passed, but the live runner did not preserve process isolation.

The live summary reduced the complete validator result to booleans and discarded the validator payload. Consequently an import-order, framework-runtime, or process-state-dependent route inventory difference was reported only as two false aggregate checks.

The available Windows evidence does not support guessing which individual route/topology sub-check differed. The missing diagnostic evidence is itself the confirmed validator defect.

## Impact

- The real Agent, model, Tool, Sandbox, ownership, cleanup, npm and portability path succeeded but STEP promotion remained blocked.
- The 75/77 result could not identify the exact failing route count or topology predicate.
- Re-running the same build would repeat manual diagnosis without producing better evidence.

## Fix

- Run `scripts/validate_step081_architecture.py` through `sys.executable` in an isolated child process.
- Set the repository root explicitly as `cwd` and first `PYTHONPATH` entry.
- Parse the complete JSON validator result.
- Require a zero exit code, valid JSON, `state=PASSED`, and exact check completion.
- Persist the complete architecture validator payload and bounded child-process diagnostic in the live Acceptance summary.
- Preserve fail-closed behavior when the process cannot start, times out, emits invalid JSON, or returns a failed validator result.

## Evidence

- `docs/evidence/STEP081A_WINDOWS_LIVE_ACCEPTANCE_75_OF_77_FAILURE_SUMMARY.json`
- `scripts/json_subprocess_validation.py`
- `scripts/run_step081_live_acceptance.py`

## Automated recurrence gates

- `tests/test_step081b_live_architecture_validator_isolation.py`
- Full deterministic Python regression
- STEP081B deterministic Acceptance
- Fresh-ZIP Acceptance
- Real Windows STEP081B live rerun
