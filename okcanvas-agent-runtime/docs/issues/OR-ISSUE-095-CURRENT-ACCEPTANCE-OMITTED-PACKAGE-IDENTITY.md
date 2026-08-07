# OR-ISSUE-095 — Current acceptance omitted package identity

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP088R1_ORGANIZATION_CONTEXT_BOUNDED_RESPONSE_AND_SAFE_MCP_DIAGNOSTIC_CLOSURE`

## Evidence

The Runtime baseline and STEP088R1 acceptance were current, but `scripts/package_source.py` retained a STEP087R1 default filename and STEP087R2 package marker. A retained test detected the drift; STEP088R1 acceptance did not execute that test and reported 24/24.

## Correction

STEP089 aligns package source identity and makes both current STEP and canonical archive basename first-class acceptance checks. The retained packaging regression is included in focused acceptance.

## Recurrence gate

- `PACKAGE_STEP == CURRENT_STEP`
- `DEFAULT_OUTPUT.name` equals the current canonical archive name
- both checks are evaluated directly by the current acceptance script
- the retained package identity test is included in focused regression
