# STEP021 — Read-only local approval inbox

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Goal

Expose persisted local Tool approval records through a bounded, read-only local-admin API and Operations Console panel without adding approval or rejection controls.

## Scope

- `GET /v1/tool-approvals` with state, limit, and offset filters;
- safe inbox metadata only: approval, submission, Task, Run, state, decision, Tool, trace, execution count, and timestamps;
- approval totals and pending count in `/v1/operations/summary`;
- read-only Approval Inbox tab in `/console`;
- deterministic acceptance and a corrected Windows launcher for STEP020 live SDK acceptance.

## Non-scope

- approval or rejection buttons;
- browser storage of the Run-submitter key;
- general local Tool registry;
- multiple interruptions or batch decisions;
- user-specific approval roles;
- automatic approval expiry;
- changing the STEP020 SDK approval state machine.

## Reference adoption

- ADAPT `examples/tools/shell_human_in_the_loop.py`: make pending approval state visible and explicit.
- ADAPT `examples/sandbox/extensions/temporal/temporal_sandbox_tui.py`: separate approval observation from execution state.
- REJECT approval buttons in the current console; decision authority stays outside the read-only surface.
- REJECT raw Tool arguments and RunState storage metadata in inbox responses.
- REJECT direct `/reference` import.

## Acceptance

- authentication required;
- exact state filtering and bounded pagination;
- safe response excludes RunState paths, key IDs, Tool call hashes, and argument hashes;
- summary pending count is accurate;
- GET requests do not mutate Product SQLite;
- Console contains no POST, decision endpoint, or Run-submitter key;
- Reference integrity remains 4/4.
