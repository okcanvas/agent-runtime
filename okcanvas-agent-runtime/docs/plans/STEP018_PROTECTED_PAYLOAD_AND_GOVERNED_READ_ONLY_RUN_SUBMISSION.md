# STEP018 — Protected Payload and Governed Read-only Run Submission

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Goal

Implement the first actual governed execution path for immutable read-only Agent definitions while keeping raw input outside SQLite and preserving exact authority, fingerprint, idempotency, integrity, and one-Task/Run boundaries.

## Reference inspection

Inspected before implementation:

- `reference/upstream/openai-agents-python-0.19.0/.agents/references/runstate-schema.md`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_state.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/entries/mounts/patterns.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tracing/traces.py`

## Reference decisions

### ADOPT

- RunState is SDK pause/resume state, not a secret store or Product Task ledger;
- no API key in persisted trace state;
- cryptographic identity may be represented by a non-secret fingerprint.

### ADAPT

- owner-only sensitive file creation into atomic encrypted payload files;
- immutable metadata binding into AES-GCM authenticated additional data;
- SDK execution service reuse after Product policy and integrity validation.

### REJECT

- raw input in SDK RunState, SQLite, Event payload, or Trace;
- direct `/reference` imports;
- authentication alone as execution authority;
- local Tool or write MCP execution in this STEP.

## Implemented

- AES-256-GCM protected payload store;
- separate Run-submitter authenticator;
- governed preflight and confirmation endpoints;
- policy/definition/model/payload integrity revalidation;
- atomic Task/Run/Event/submission binding;
- compare-and-set execution claim;
- idempotent replay and concurrent confirmation protection;
- existing generic Agent scheduling and Artifact completion;
- deterministic acceptance and Windows launcher.

## Acceptance

`sh_run_step018_acceptance.cmd` validates 22 checks covering authority separation, encryption, absence of raw input and keys, zero Task/Run during preflight, exact confirmation, one Task/Run, one scheduler invocation, replay, Artifact completion, tamper rejection, direct API denial, read-only console, and unchanged Reference trees.

## Explicit non-scope

- payload expiry/deletion;
- stale claim recovery;
- multi-process/distributed lease;
- local Tool approval execution;
- console mutation;
- write MCP, Handoff, Session, or Codex-write execution.
