# STEP091B3 Implementation Failure Log

## Purpose

Record every failure observed while implementing and packaging STEP091B3 so the same
class of error is not repeated in later storage waves.

## Recorded failures

### F1 — STEP081 physical manifest did not include the new PostgreSQL modules

- Symptom: architecture validation returned 38/40.
- False checks: `identity_exact`, `physical_module_inventory_current`.
- Cause: current baseline constants and the physical canonical-module manifest still
  described STEP091C.
- Correction: update only the current validated identity and regenerate the physical
  manifest from the retained STEP081 relocation evidence.
- Prevention: every new canonical Python module must be followed by STEP081 physical
  manifest regeneration before running focused regression.

### F2 — Direct acceptance execution exceeded the outer command window

- Symptom: the acceptance process reached focused regression and the outer tool call
  ended before JSON evidence was written.
- Cause: duplicate execution of a focused suite already proven separately.
- Correction: persist bounded focused evidence and supply it through the acceptance
  script's explicit `--focused-evidence` input.
- Prevention: long acceptance gates must support cryptographically bounded reusable
  subprocess evidence rather than depending on one monolithic command window.

### F3 — Partition wrapper was interrupted although individual pytest groups were healthy

- Symptom: a multi-partition shell call ended after completed partitions.
- Cause: external command-window behavior, not a pytest failure.
- Correction: retain each partition's independent JSON/log evidence and continue only
  missing partition numbers.
- Prevention: never discard completed partition evidence when an outer grouped call ends.

### F4 — Historical STEP084/STEP089 tests fixed the previous current ZIP name

- Symptom: partition 11 reported one failure while 118 tests passed.
- Cause: current package identity assertions still expected the STEP091C ZIP name.
- Correction: update only the current package-name expectations to STEP091B3 and rerun
  the affected partition.
- Prevention: historical capability tests may retain capability semantics, but any
  assertion intentionally checking the current package identity must follow the current
  baseline constants.
