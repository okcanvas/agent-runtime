# STEP065 — Strict Session History Key Rotation and Recovery V1

## Baseline

- Version: `2.45.0`
- Current STEP: `STEP065_STRICT_SESSION_HISTORY_KEY_ROTATION_AND_RECOVERY_V1`
- Predecessor: STEP064A Windows live accepted.

## Problem proven by the current code

STEP063 binds every Product Session to one non-secret `history_encryption_key_id`. The normal Session lifecycle rejects a changed key ID at binding, acquire, assertion, item-count update, and release. Before STEP065, changing `OKCANVAS_SESSION_HISTORY_KEY` therefore made every existing Session unusable. The only recovery was destructive clear.

The pinned SDK SQLiteSession stores all Sessions in one `history.sqlite3` using `agent_sessions`, `agent_messages`, and `message_data`. Normal SDK reads skip malformed JSON. A key-rotation operator therefore cannot safely depend on the SDK read API because every physical row must be inspected and rewritten or rejected.

## Selected scope

STEP065 adds one explicit single-Session operation:

```text
POST /v1/sessions/{session_id}/rotate-history-key
```

The process starts with:

```text
OKCANVAS_SESSION_HISTORY_KEY          = target/current key
OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY = source/previous key
```

Both keys are external 32-byte values. Neither raw key is accepted in an HTTP body, persisted, emitted, or returned. The response exposes only 16-hex SHA-256 key IDs and item counts.

## Durable recovery protocol

1. Verify the Session is ACTIVE and has no active Turn or compaction lease.
2. Insert a product-owned `product_session_key_rotation` intent row.
3. Fence the Session through `active_run_id=session_rotation_<uuid>`.
4. Open the pinned SDK history database directly.
5. Inspect every physical `message_data` row; plaintext, malformed JSON, mixed keys, unexpected keys, and more than 256 items fail closed.
6. Re-encrypt all rows in one history-database transaction.
7. Verify every rewritten envelope with the target key before commit.
8. Update the Product Session key ID and item count, remove the lease and intent row.

Crash recovery is deterministic:

- all source-key rows: retry requires the previous key and repeats the atomic rewrite;
- all target-key rows: finalize the catalog without the previous key;
- mixed or unknown rows: reject and require explicit clear.

An incomplete rotation can be explicitly cleared without decrypting. Automatic rotation, batch rotation, startup scanning, background work, TTL, key storage, raw-history events, and external Session backends remain disabled.

## Acceptance

The STEP065 gate must prove policy/source integrity, exact SDK schema binding, distinct-key validation, successful re-encryption, no plaintext persistence, active-Turn fencing, interrupted-operation resume, mixed-key fail-closed behavior, destructive clear recovery, bounded item count, API authority, no secret response fields, historical Session/compaction regressions, Node release integrity, and unchanged References.
