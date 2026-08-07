# STEP023 — Minimal local approval operator CLI

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Goal

Provide the smallest safe human-operated decision surface over the existing STEP020 approval API without adding browser mutations, a general approval platform, or new Agent/Tool capability.

## Scope

- list bounded approval Inbox metadata through the existing local Control API;
- derive exact approve/reject confirmation challenges from `approval_id` and `run_id`;
- approve or reject exactly one approval at a time;
- require both local-admin and Run-submitter authorities for a decision;
- restrict credential-bearing traffic to an explicit loopback URL;
- enforce the exact confirmation again on the server, not only in the CLI;
- preserve the read-only Operations Console.

## Non-scope

- browser approval/rejection buttons;
- batch decisions;
- approval expiry, escalation, delegation, or role administration;
- multiple simultaneous SDK interruptions;
- new local Tools, write MCP, Handoff, Session, shell, filesystem, or network capability;
- remote Control API operation.

## Reference adoption

- ADAPT `reference/upstream/openai-agents-python-0.19.0/examples/tools/shell_human_in_the_loop.py`: require an explicit operator decision for each interruption and never infer approval.
- ADAPT `reference/upstream/openai-agents-python-0.19.0/examples/sandbox/extensions/temporal/temporal_sandbox_tui.py`: separate observation from decision and show the pending item before accepting a decision.
- REJECT broad interactive approval UI and `always_approve`/`always_reject` behavior.
- REJECT direct import or execution from `/reference`.

## Decision confirmation

```text
APPROVE <approval_id> <run_id>
REJECT  <approval_id> <run_id>
```

The CLI checks this exact value before POST. The Control API independently checks the same value before claiming the approval decision. A mismatch leaves the approval `PENDING` and executes the Tool zero times.

## Loopback boundary

The operator client accepts only `localhost`, `127.0.0.0/8`, or `::1` with an explicit port. It rejects remote hostnames, embedded credentials, URL paths, query strings, and fragments so local authority keys cannot be sent to an arbitrary server.

## Acceptance

- actual loopback HTTP server started and stopped cleanly;
- two pending approvals listed through the operator client;
- Inbox payload excludes RunState/storage/Tool payload metadata;
- wrong confirmation is blocked and does not consume the approval;
- approve executes the Tool exactly once and replay is idempotent;
- reject executes the Tool zero times;
- no pending approvals remain;
- authority keys are absent from SQLite and compact Evidence;
- Reference integrity remains 4/4;
- Acceptance Workspace cleanup is `COMPLETED`.
