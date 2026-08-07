# ADR-012 — Encrypted SDK RunState and generation-fenced Tool approval

Status: Accepted in STEP020.

## Decision

Use the installed OpenAI Agents SDK `needs_approval`, `RunState.to_json()`, `RunState.from_json()`, `approve()`, and `reject()` contracts. Persist RunState only as an AES-256-GCM encrypted file under the configured run-state root. Keep Product Task/Run and approval metadata in SQLite, but never store RunState plaintext, request text, raw Tool arguments, raw call IDs, encryption keys, or raw resume tokens there.

An approval decision claims a new resume generation. SQLite stores only its token SHA-256. The approved Tool body must atomically change persisted Tool execution count from zero to one while presenting that generation token. Repeated or stale processes cannot enter the Tool body.

## Reason

SDK RunState is the authoritative pause/resume boundary, while Product state remains the operational ledger. Encryption protects SDK state because it can contain provider and conversation state. Generation fencing closes the duplicate Tool-entry gap across process restarts without claiming distributed exactly-once execution.

## Rejected

- storing raw RunState JSON in SQLite;
- using Product Events as the RunState store;
- placing raw protected request text in RunState context;
- approving arbitrary local Tools;
- treating the standalone STEP004 file lock as the final Product approval ledger;
- direct imports from `/reference`.
