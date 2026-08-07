# OR-ISSUE-093 — Groupware read Agent shared a write-capable output contract

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Discovered in

STEP086R1 read-only boundary audit

## Failure

`groupware-read-agent` used `OrganizationAssistantResult`. That schema includes `WRITE_ACTION`, reversible/irreversible side effects, proposed actions and pending approvals. Instructions prohibited those values, but a write-shaped model output could still pass schema validation.

## Root cause

Read-only safety was expressed in instructions and Tool allowlists but not in the final output type. The generic runtime correctly enforced the declared Pydantic contract; the declared contract itself was too broad for this Agent.

## Correction

- Added Product-owned `GroupwareReadResult`.
- `request_class` is fixed to `READ_SYSTEM` and `side_effect` is fixed to `READ`.
- action, approval, mutation and automation fields do not exist.
- non-empty results require an actual read operation and enterprise citations.
- capability-limited/refused results cannot claim records.
- `AgentDefinitionCatalog` now rejects any drift from the exact Groupware read Sub-agent contract.

## Recurrence gate

- output registry and JSON-schema equality tests
- write-shaped output rejection tests
- Agent-definition tamper test
- STEP086R1 Groupware boundary validator
