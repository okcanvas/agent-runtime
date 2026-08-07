# STEP063 Code Audit — Strict Encrypted SQLite Session History V1

## Audited current implementation

### Product catalog and SDK backend

- `src/okcanvas_agent_runtime/sessions/service.py` owns Product Session state in `catalog.sqlite3`.
- `raw_sdk_session()` constructs the installed SDK `SQLiteSession` against `history.sqlite3`.
- Before STEP063, the SDK backend received normal Runner items and therefore stored their JSON content directly.

### Policy evidence

`specs/runtime/sqlite-session-policy.json` previously identified encryption and compaction as disabled. STEP063 changes the policy to schema v2 and binds:

```text
policy_id                 local-strict-encrypted-sqlite-session-v1
encryption_mode           STRICT_AES_256_GCM_HKDF_SHA256_V1
envelope_version          1
key_derivation            PER_SESSION_HKDF_SHA256_V1
legacy_plaintext_mode     REJECT
ttl_seconds               null
compaction_enabled        false
```

### Upstream SDK reference decision

The retained OpenAI Agents SDK 0.19.0 memory examples and `EncryptedSession` implementation were inspected. The SDK abstraction is useful, but its permissive legacy plaintext handling, invalid/expired-item skipping and TTL semantics do not satisfy this Runtime's fail-closed persistence constitution. STEP063 therefore adapts the SDK Session protocol while retaining the installed SDK SQLite storage backend.

## Implemented cryptographic boundary

`src/okcanvas_agent_runtime/sessions/encryption.py` provides:

- exact 32-byte external key parsing;
- 16-hex non-secret key ID;
- HKDF-SHA256 per-Session derivation;
- AES-256-GCM with 12-byte random nonce;
- exact envelope keys only;
- AAD containing schema version, Session ID, key ID and envelope version;
- strict authenticated decrypt with no skip path.

The key itself is never written to SQLite, Events, artifacts or public contracts.

## Lifecycle audit

`SQLiteSessionRuntimeService` requires and validates the key at:

- Session create;
- binding validation;
- Turn acquire;
- active-Turn assertion;
- active item-count update;
- Turn release;
- encrypted history read/count/rollback.

`clear()` deliberately uses the raw SDK backend without decrypting so legacy or corrupt history can be removed. Active-Turn and state fencing remain unchanged.

## Key separation

`scripts/windows_entrypoint.py` rejects equal configured session-history and protected-payload keys. `control_api.create_app()` repeats the same cryptographic-material comparison so callers cannot bypass the environment launcher boundary.

## Compatibility audit

The following deterministic acceptances were run through the strict wrapper:

```text
STEP043 SQLite Session continuity
STEP046 Session + Approval
STEP047 Session + native Handoff
STEP048 Session + Guardrail
STEP049 Session + Agent-as-Tool
STEP050 Session + MCP
```

The existing Product Run, Invocation, Event, Artifact, evaluation, lease, rollback, clear and payload-retention behavior remains intact.

## Security limitations retained explicitly

- The operator must retain the external key. Losing it makes active encrypted history unreadable; clear remains possible.
- There is no automatic key rotation or recovery escrow.
- SQLite file metadata and item counts are not encrypted.
- Compaction and external Session backends remain deferred.
- This STEP does not claim filesystem-level encryption; item confidentiality and integrity are provided by AES-256-GCM envelopes.
