# STEP063 — Strict Encrypted SQLite Session History V1

## Baseline

- predecessor: `STEP062C_COMMITTED_NODE_DIST_RELEASE_INTEGRITY_ACCEPTANCE_FIX` / `2.42.3` / Windows-live accepted;
- current version: `2.43.0`;
- current STEP: `STEP063_STRICT_ENCRYPTED_SQLITE_SESSION_HISTORY_V1`;
- state before Windows evidence: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`.

## Code-audited problem

The Product Session catalog was governed, but the installed SDK `SQLiteSession` persisted each conversation item as plaintext JSON in `history.sqlite3`. The policy and RuntimeInfo explicitly reported encryption as disabled. That makes long-lived Session continuity unsuitable for organization use even though raw history is excluded from Product Events.

The immutable OpenAI Agents SDK 0.19.0 reference includes an optional `EncryptedSession`, but direct adoption is rejected for this product boundary because it accepts legacy plaintext items, can skip expired or invalid ciphertext, and is TTL-oriented. OKCanvas requires deterministic fail-closed behavior.

## Implemented scope

1. External 32-byte `OKCANVAS_SESSION_HISTORY_KEY` with non-secret key ID.
2. Per-Session HKDF-SHA256 derivation.
3. Exact AES-256-GCM item envelope with authenticated Session identity.
4. Strict plaintext, key mismatch, malformed envelope and tamper rejection.
5. Catalog migration adding `history_encryption_key_id`.
6. Pre-encryption Session resume rejection with explicit clear/recreate path.
7. Key validation at all Turn lifecycle mutation boundaries.
8. Key separation from the protected-payload key.
9. Runtime binding, API, Node CLI and Windows environment visibility.
10. Existing Session/Approval/Handoff/Guardrail/Agent-as-Tool/MCP composition regression closure.

## Explicit non-scope

- history compaction;
- TTL expiration;
- automatic legacy plaintext migration;
- online key rotation or re-encryption;
- Redis, MongoDB, SQLAlchemy, Dapr or hosted Session backend;
- history export or raw-history admin API;
- changes to STEP062 orchestration.

## Acceptance

```cmd
sh_run_step063_acceptance.cmd
```

The acceptance must require no real OpenAI model call. It verifies encryption storage, fail-closed corruption behavior, lifecycle key fencing, predecessor Windows evidence, historical Session compositions, Node release integrity, immutable References and complete documentation.

## Next-step rule

Do not select STEP064 before complete Windows acceptance and a fresh audit of the packaged STEP063 ZIP.
