# OR-ISSUE-086 — Historical launcher test hard-coded the STEP085 current pair

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`

## Discovered in

`STEP086_GROUPWARE_READ_ONLY_VERTICAL`

## Failure

After the launcher registry correctly promoted STEP086, the preserved STEP081 launcher-registry test still required these literal paths:

- `scripts/run_step085_acceptance.py`
- `sh_run_step085_acceptance.cmd`

The executable launcher registry validator itself passed 7/7, but preserved STEP081 and STEP081C regressions failed because they encoded a temporary current baseline as a permanent invariant.

## Root cause

The test correctly owned the invariant that there must be exactly one current Python acceptance script and one current Windows launcher, but it incorrectly froze the STEP085 token instead of deriving the pair from `current_step_token` in the launcher registry SOT.

## Correction

The regression now derives the expected current paths from `specs/acceptance/launcher-registry.json.current_step_token`. STEP086 also adds a direct Windows-entrypoint regression for:

- the `groupware-readonly-acceptance` command,
- dispatch to `scripts/run_step086_acceptance.py`, and
- allowlisted loading of `OKCANVAS_GROUPWARE_READ_BEARER` without executing the environment file.

## Recurrence gate

- `tests/test_step081_windows_entrypoint_and_launcher_registry.py`
- `tests/test_step081c_windows_deterministic_architecture_diagnostics_and_topology_normalization.py`
- `tests/test_step086_groupware_read_only_vertical.py`
- `scripts/validate_acceptance_launcher_registry.py`
