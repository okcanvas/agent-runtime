# OR-ISSUE-098 — Final HANDOFF omitted the external Provider deployment identifier

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP086R2_DELEGATED_ROLE_HEADER_AND_EXTERNAL_CONNECTOR_CONTRACT_CLOSURE`

## Evidence

The first final Fresh validation passed 17/18 checks after source and Fresh Python regression both passed 978/978. The remaining check failed because `HANDOFF.md` described the external Connector in prose but omitted the exact retained identifier `external-connector-service`.

## Root cause

The finalization Gate required an exact deployment identity that was not also asserted by a source-tree regression. This repeated the broader final-HANDOFF identity-loss class recorded by OR-ISSUE-067 and OR-ISSUE-091.

## Correction

- Added exact Provider deployment, Connector project, example status and example path identifiers to `HANDOFF.md`.
- Added a source regression requiring all four identifiers.
- Invalidated and reran source regression, Compliance, packaging and Fresh regression.

## Recurrence gate

- `test_step086r2_handoff_preserves_exact_external_connector_and_example_identifiers`
- final Fresh HANDOFF identity Gate
- full source and Fresh Python regression
