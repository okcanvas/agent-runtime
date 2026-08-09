# STEP008R4R10C implementation failure log

## R10B actual Windows failure

- Stage: `execute_establish-employee-focus`
- CLI process return code: `0`
- CLI completed Product requests: `0`
- Runtime Run count: `0`
- Product error: `RUN_SUBMISSION_INVALID — Session Agent or Runtime binding changed`

Root cause: harness Session creation used `organization-assistant-session-agent` while Organization Context
routing selected `organization-context-session-agent`. Strict Session binding correctly rejected admission.

## Corrective rule

A cross-domain conversation has one canonical Session root. Domain changes select a stateless child inside
that root; they never switch the root Agent, Session ID, or stable focus owner.

## Static validator mistake during implementation

The first STEP094R1 static validator searched the gateway file for an error string owned by
`cross_domain_session.py`, producing 11/12. The validator was corrected to inspect the canonical owner file;
Product code was not changed for that validator failure.

## Current SOT drift caught before packaging

Static package review found two current-SOT fields still describing the parent topology: `project-catalog.json` kept Runtime STEP094/2.78.0, and the current Organization Context integration contract kept `organization-context-session-agent` plus the old single-domain execution path. `current-baseline.json` also retained the R10A source-release SHA although R10C is based on the final R10B release. The canonical SOT records were corrected directly; no alias, validator exemption or compatibility fallback was added. The R10C workspace static validator now checks these fields.
