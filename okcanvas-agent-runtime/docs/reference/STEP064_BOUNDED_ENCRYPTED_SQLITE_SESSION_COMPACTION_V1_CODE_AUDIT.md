# STEP064 Code Audit — Bounded Encrypted SQLite Session Compaction V1

## Audited baseline

The implementation started only after the user-reported Windows closure of STEP063A. The accepted predecessor evidence is retained at `docs/evidence/STEP063A_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.

Required sources inspected before selection:

- `HANDOFF.md`, `PLANS.md`, `docs/plans/ROADMAP.md`;
- STEP061 examples coverage matrix;
- `sessions/service.py`, `sessions/encryption.py`, Session policy and all composition tests;
- generic execution and approval resume transaction boundaries;
- pinned SDK compaction examples and `openai_responses_compaction_session.py`;
- SDK Runner Session persistence hooks.

## Findings

### 1. Unencrypted history was already closed

STEP063 stores each SDK SQLite history item through the product-owned strict AES-256-GCM wrapper. The encryption implementation remains byte-identical in STEP064:

```text
b2127cf828e1e4d44663295edac0b4451d8b452a352e73789b3272d6e7a781b0
src/okcanvas_agent_runtime/sessions/encryption.py
```

### 2. Long-lived history had no reduction path

The current Product Session catalog tracked an ever-growing `item_count`; policy explicitly had compaction disabled. External Session backends would relocate this growth but would not solve it. Compaction therefore precedes Redis/MongoDB/SQLAlchemy/Dapr or hosted Session work.

### 3. Direct SDK automatic compaction conflicts with Product rollback

The pinned SDK can defer compaction from Runner and replace underlying history after a turn. OKCanvas, however, may still fail after Runner returns while writing Artifact or transitioning Product state. Existing failed-turn recovery uses the pre-Turn item count. If automatic compaction had already reduced history, rollback would see a history shorter than its boundary and fail.

Conclusion: the SDK decorator may be used as a compaction primitive, but it must not be passed to Runner.

### 4. Post-release compaction needs a concurrency fence

Releasing the Product Turn before compaction makes the item-count rollback safe, but it also permits a second Turn to start while encrypted history is being replaced. STEP064 therefore atomically reuses `active_run_id` with the same still-running Product Run as a short maintenance lease. Existing `acquire_turn()` and `clear()` rules then block concurrent mutation without a second lock system.

## Implemented files

### Policy and contracts

- `specs/runtime/sqlite-session-policy.json`
- `sessions/models.py`
- `sessions/policy.py`

Policy SHA-256:

```text
379e868d22b7b6c216fe2988d875846ed021f53cd8cb86f5630c399f68519d99
```

### Compaction facade

- `sessions/compaction.py`

Responsibilities:

- exact candidate selector from SDK 0.19.0;
- trigger 10 and maximum 256 total input items;
- explicit input mode and `store=false`;
- provider response ID rejection;
- lazy SDK compactor creation;
- strict non-empty reduction;
- exact history restoration and verification;
- metadata-only started/failed events.

### Product Session integration

- `sessions/service.py`

`compact_after_committed_turn()`:

- acquires a DB lease only after the normal Turn release;
- blocks concurrent Turn/clear through existing `active_run_id` semantics;
- runs bounded compaction;
- updates catalog `item_count` only after verified replacement;
- emits completed metadata only after catalog commit;
- releases the lease after routine failure without changing the committed Turn count.

### Execution paths

- `execution/service.py`
- `tool_approval/service.py`
- `execution/openai_gateway.py`

The gateway still passes `session_runtime.sdk_session(session_id)`, which is encryption-only. Generic successful Session execution invokes compaction after `session.turn.completed` and before `run.completed`. Approval rejection and approval success do the same after their committed Session Turn. Failure rollback paths do not compact.

### Runtime binding

- `execution/runtime_binding.py`

The new compaction module is included in all six Session-capable binding source sets, so a change to compaction code changes executable Runtime identity.

## Provider behavior

The factory constructs:

```text
AsyncOpenAI(
  base_url=https://api.openai.com/v1,
  max_retries=0
)
OpenAIResponsesCompactionSession(
  model=gpt-4.1,
  compaction_mode=input
)
```

Creation is lazy. No external call occurs below the trigger. Deterministic tests replace both SDK and OpenAI clients with fakes and inspect the exact arguments.

## Usage accounting

The pinned `responses.compact` path returns compacted output but does not expose a Runner-style `Usage` object through `OpenAIResponsesCompactionSession.run_compaction()`. STEP064 records one provider request in lifecycle metadata but explicitly records `provider_token_usage_recorded=false`; it does not fabricate token counts or merge unknown usage into Run usage.

## Security and privacy

- encrypted SQLite remains the only local history store;
- decrypted items exist only in process memory for the provider request and validation;
- Product events contain no history;
- provider response IDs are rejected;
- `store=false` remains mandatory;
- unsupported mode, oversized input and invalid output fail closed;
- Reference source is never imported by Product code.

## Test evidence

Focused tests cover policy, candidate selection, encrypted storage, exact provider arguments, threshold, maximum input, non-reducing restore, forbidden response IDs, lazy factory, DB lease, failure lease release and source-level transaction ordering.

Historical SQLite Session runtime and Approval/Handoff/Guardrail/Agent-as-Tool/MCP composition tests remain in the acceptance gate.

## Unverified live boundary

No real `responses.compact` request was made in the deterministic environment. Windows acceptance verifies packaging, Python behavior, committed Node release and cross-platform launch; a real paid provider compaction acceptance is a separate future decision, not silently claimed here.

## Next-step lock

STEP065 is not selected. Selection requires Windows STEP064 evidence and a fresh audit of this exact packaged ZIP.
