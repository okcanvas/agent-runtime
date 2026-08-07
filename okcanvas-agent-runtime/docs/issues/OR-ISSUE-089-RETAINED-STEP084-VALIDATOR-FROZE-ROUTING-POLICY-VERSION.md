# OR-ISSUE-089 — Retained STEP084 validator froze routing policy version 1.1.0

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`

## Discovered in

`STEP086_GROUPWARE_READ_ONLY_VERTICAL`

## Failure

The retained STEP084 organization-context validator required routing policy version 1.1.0. STEP086 legitimately advances the same policy to 1.2.0 to add Groupware read-only classification, so the historical promotion assertion becomes false even though all organization grounding contracts remain valid.

## Root cause

A historical current-version assertion was included in a cumulative retained-feature projection.

## Correction

STEP086 acceptance excludes only `routing_policy_promoted` from the retained STEP084 projection and independently validates the current 1.2.0 Groupware routing policy through the STEP086 validator. The remaining seventeen organization-context contracts must still pass.

## Recurrence gate

- `scripts/run_step086_acceptance.py`
- `scripts/validate_step086_groupware_read_only.py`
- retained STEP084 organization-context 17/17 projection
