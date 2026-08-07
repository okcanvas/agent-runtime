# WORKSPACE-ISSUE-013 — Integrated runner redundantly nested full Runtime acceptance

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Evidence

The first STEP003 integrated Workspace runner nested the complete Runtime STEP087 acceptance before Product CLI, Connector, Example and two E2E suites. The outer process produced no final payload before the 900-second execution boundary expired. No Product failure evidence was emitted.

## Root cause

The Workspace runner duplicated a completed, separately evidenced Runtime acceptance inside a larger sequential acceptance. This made the Workspace gate unbounded by composition and obscured which child phase consumed the execution window.

## Correction

- Keep `okcanvas-agent-runtime/docs/evidence/STEP087_DETERMINISTIC_ACCEPTANCE.json` as the exact Runtime 15/15 evidence.
- Include that file in the Runtime parent byte manifest.
- Validate its STEP, version, state and 15/15 count in Workspace acceptance.
- Re-run only Workspace-owned tests and cross-project Product/Connector/Example/E2E gates.

The corrected runner completed 22/22.

## Recurrence gate

Workspace tests require the STEP003 runner to reference the exact STEP087 evidence and forbid invoking `run_step087_acceptance.py` from the integrated runner.

## STEP004 recurrence and second closure

The first STEP004 readiness draft repeated the same composition error with `run_step087r1_acceptance.py`. No Product failure occurred, but the nested Runtime gate emitted approximately 748 KB of duplicated evidence and varied from about 23 seconds to more than 80 seconds under load, pushing the outer Workspace run toward execution limits.

The STEP004 runner now reads the immutable `STEP087R1_DETERMINISTIC_ACCEPTANCE.json`, verifies its exact 17/17 state, and relies on the Runtime parent byte manifest for source/evidence binding. Workspace-owned unit, subproject and cross-project E2E gates remain freshly executed. The corrected STEP004 readiness completed 29/29 in 14.73 seconds before the additional recurrence unit was added.

The STEP004 unit suite explicitly forbids a nested `run_step087r1_acceptance.py` invocation and requires the exact retained STEP087R1 evidence path.
