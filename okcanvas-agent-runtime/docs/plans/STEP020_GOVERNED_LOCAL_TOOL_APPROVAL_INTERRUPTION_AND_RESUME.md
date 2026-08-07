# STEP020 — Governed Local Tool Approval Interruption and Resume

Status: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Scope completed

- one immutable local Tool Agent definition;
- one read-only Function Tool with SDK `needs_approval=true`;
- encrypted protected request for approval-interrupted submissions;
- one Product Task/Run created before SDK interruption;
- Product `WAITING_APPROVAL` / `INTERRUPTED` states;
- encrypted persisted SDK RunState;
- explicit approve/reject APIs;
- separate-process deterministic resume acceptance;
- generation-fenced Tool entry and exactly-one execution count;
- approval success Artifact and standard retention lifecycle;
- rejection without Tool execution;
- tamper failure preservation;
- direct `/reference` import prohibition and Reference integrity verification.

## Non-scope

General Tool authoring, multiple pending Tool calls, write/shell Tools, remote MCP approval, Handoff, Session, automatic startup resume, distributed worker leases, and Operations Console mutations.
