# STEP065 Code Audit — Strict Session History Key Rotation and Recovery V1

## Audited predecessor

`STEP064A_PYTEST_ASYNC_PLUGIN_INDEPENDENCE_FIX`, version `2.44.1`, Windows live accepted.

## Code findings

### Existing fail-closed key fence

`src/okcanvas_agent_runtime/sessions/service.py` compares each Session catalog `history_encryption_key_id` with the configured key. A mismatch rejects normal execution. `tests/test_sqlite_session_runtime.py::test_history_key_rotation_fails_existing_session` explicitly proved that rotation was unsupported.

### Physical SDK storage contract

Pinned source:

```text
reference/upstream/openai-agents-python-0.19.0/src/agents/memory/sqlite_session.py
SHA-256 55e998777c4d15e667b819965b1bd5d66c7391969e4cd270fdd1a6498dccbf16
```

The source owns `agent_sessions`, `agent_messages`, and `message_data`. Its normal `get_items()` skips malformed JSON. STEP065 therefore binds the exact source SHA and validates every physical row directly instead of relying on a potentially lossy read.

### Chosen recovery model

A product-owned intent table plus the existing `active_run_id` lease separates catalog intent from one-database atomic history rewriting. This handles process termination between the history commit and catalog finalize:

```text
catalog intent old→new + lease
history all old or all new
retry inspects physical envelope key IDs
```

No mixed history can result from the rewrite transaction itself. Mixed pre-existing data is rejected.

## New implementation

- `specs/runtime/sqlite-session-key-rotation-policy.json`
- `src/okcanvas_agent_runtime/sessions/rotation_policy.py`
- `src/okcanvas_agent_runtime/sessions/rotation.py`
- `product_session_key_rotation` catalog table
- `SQLiteSessionRuntimeService.rotate_history_key()`
- `POST /v1/sessions/{session_id}/rotate-history-key`
- optional `OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY`

## Security boundaries

- current, previous, and protected-payload keys must be pairwise distinct;
- raw keys never enter API requests, responses, catalog rows, events, Artifacts, or documentation evidence;
- every envelope remains AES-256-GCM/HKDF bound to its Session ID;
- maximum rotation input is 256 physical rows;
- rotation is explicit, single-Session, authenticated by admin and run-submitter authorities;
- an active Turn or maintenance lease blocks a new rotation;
- malformed JSON, plaintext, unsupported envelopes, invalid tags, mixed IDs, and unexpected IDs fail closed;
- incomplete rotation may be explicitly cleared without decryption.

## Deliberate exclusions

- automatic or startup rotation;
- batch/all-Session rotation;
- persisted key vault or KMS integration;
- rotation while a Turn or compaction is active;
- raw-history export or event payloads;
- external Session backend migration;
- remote/hosted MCP work.

## Final implementation audit note

The policy mode check executes before the catalog transaction. An invalid injected policy therefore cannot leave a durable rotation intent or maintenance lease. Existing-test baseline changes were mechanically limited to version/STEP advancement, except the STEP064A historical test, which also records its now-Windows-live status and the current Session service SHA.
