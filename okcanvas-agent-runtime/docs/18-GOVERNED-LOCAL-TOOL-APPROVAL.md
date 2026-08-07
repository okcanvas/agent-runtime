# Governed Local Tool Approval

STEP020 integrates the official OpenAI Agents SDK `needs_approval` / `RunState` pause-and-resume boundary with Product Task, Run, Event, protected payload, and retention state.

## Controlled vertical slice

Only `local-text-metrics-agent` and its single `local_text_metrics` Function Tool are executable. The Tool is deterministic and read-only. It computes the SHA-256, character count, word count, and line count of the already-authorized protected request. It has no filesystem, network, shell, MCP, Handoff, or Session access.

## Lifecycle

1. Run-submission preflight encrypts the request and returns `APPROVAL_INTERRUPTED`.
2. Approval preparation creates one Task/Run, obtains the existing generation-fenced pre-start claim, starts the SDK, and interrupts before the Tool body.
3. SDK `RunState` is serialized with an opaque context only, encrypted with AES-256-GCM, and stored outside SQLite and Product Events.
4. Product Task becomes `WAITING_APPROVAL`; Product Run becomes `INTERRUPTED`.
5. A later process explicitly approves or rejects.
6. A new approval-resume generation token is stored only as SHA-256. The Tool body atomically claims execution count `0→1` immediately before execution.
7. Approval resumes the SDK and creates the normal final-output Artifact. Rejection resumes SDK rejection handling but never enters the Tool body.

## Persisted data

SQLite stores approval identity, Tool name, hashes of call ID and arguments, encrypted RunState reference/SHA/byte length/key fingerprint, decision, lifecycle timestamps, and Tool execution count. It does not store raw request, raw Tool arguments, raw Tool call ID, RunState plaintext, encryption key, or resume token.

## Product events

- `tool.approval.requested`
- `run.interrupted`
- `tool.approval.decided`
- `run.resumed`
- normal `tool.started` / `tool.completed` only after approval

## Failure policy

Encrypted RunState tampering fails closed, transitions the Product Run/Task to `FAILED`, preserves the encrypted state file as evidence, and does not execute the Tool. Completed approval decisions are idempotent only for the same decision; an opposite terminal decision is rejected.

## Explicit limits

STEP020 supports one controlled local read-only Tool and one whole Tool-call decision. It does not implement a general Tool registry, multiple interruptions, batch approvals, per-user approval roles, distributed resume leasing, automatic startup resume, write Tools, shell Tools, Handoffs, Sessions, or console decision buttons.

## Operator decision confirmation

STEP023 requires an exact `APPROVE|REJECT <approval_id> <run_id>` confirmation in addition to both local authorities. The Control API validates it before claiming the decision. A mismatch leaves the approval pending and executes the Tool zero times.


## STEP046 SQLite Session composition

A single `ALWAYS` Function Tool may now be combined with `session_mode=sqlite-v1` only through `sqlite-session-approval-execution-v1`.

The Session Turn lease is held while approval is pending. Prepare and resume receive the same SDK Session; the approval record stores `session_id` and the pre-Turn item-count rollback boundary. Approve commits one Turn and executes the Tool once. Reject commits one conversational rejection Turn and executes the Tool zero times. Integrity/resume failure rolls SDK history back and releases the Turn without incrementing it.

The approval inbox exposes Session identity only. Raw Session history remains exclusively in the SDK Session database and is never copied into approval metadata or Product Events.
