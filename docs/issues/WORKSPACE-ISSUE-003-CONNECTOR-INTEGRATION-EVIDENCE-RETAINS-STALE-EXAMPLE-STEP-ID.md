# WORKSPACE-ISSUE-003 — Connector integration evidence retains stale Example step ID

## Finding

The accepted Connector-to-Example integration passes 7/7, but its payload reports
`example_step=EXAMPLE_STEP001_GROUPWARE_API_FAKE_TEMPLATE`. The accepted Example baseline is now
`EXAMPLE_STEP001R1_TYPESCRIPT_BUILD_DEPENDENCY_CLOSURE` / `0.1.1`.

## Scope decision

WORKSPACE STEP001 is a byte-preserving structural reassembly. Changing the Connector script would
create a new Connector product baseline, so this issue is recorded without modifying the accepted
Connector parent.

## Required next correction

A future Connector corrective step must source the Example identity from one explicit contract or
argument and add a recurrence test that rejects stale Example step/version identifiers.

## Current impact

No runtime or integration behavior failure. The actual Connector-to-Example call, delegated identity,
request redaction, result normalization, and fault mapping all pass 7/7. The defect is evidence identity
staleness only.
