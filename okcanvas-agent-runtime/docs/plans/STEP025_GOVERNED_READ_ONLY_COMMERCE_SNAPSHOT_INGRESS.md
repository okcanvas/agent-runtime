# STEP025 — Governed read-only commerce snapshot ingress boundary

## Status

`WINDOWS_LIVE_ACCEPTED`

## Implemented decision

The OpenAI Agents SDK MCP implementation was inspected under `/reference`. It exposes MCP as a Runner-internal model Tool path. That path is not used as the source of truth because STEP024B confirmation and deterministic recovery require the complete snapshot before Runner execution.

STEP025 therefore implements a product-owned pre-execution HTTP ingress. It is not an Agent Tool and performs no model call.

## Exact flow

```text
explicit controlled-commerce-http + snapshot key
→ one loopback GET
→ strict response limits and StoreReplenishmentInput validation
→ canonical JSON
→ adapter/request/snapshot identity binding
→ encrypted protected-payload preflight
→ exact confirmation
→ unchanged replenishment Agent
```

## Identity fields

The submission fingerprint and persisted bounded metadata contain:

- source adapter ID;
- source adapter version;
- adapter definition SHA-256;
- canonical source-request SHA-256;
- canonical snapshot SHA-256;
- acquisition timestamp, persisted as observation only and excluded from the fingerprint.

`input_sha256` must equal `source_snapshot_sha256`.

## Credential boundary

The immutable adapter specification contains only the environment variable names. Runtime values come from:

- `OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL`;
- `OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN`.

The URL and credential are not persisted in SQLite, Events, Artifacts, adapter files, or source ZIPs.

## Replay behavior

A same-key replay checks adapter identity, source-request hash, fixed Agent, and model before any network call. A matching replay returns the existing preflight; a mismatch conflicts. Same-key in-process concurrency shares one acquisition lock. An active preflight whose encrypted payload is missing fails closed rather than reading a potentially changed snapshot.

## Deterministic acceptance

`STEP025_ACCEPTANCE.json` proves 21 checks including one source GET, zero source writes, no second read on replay, no Task/Run before confirmation, exact identity/hash binding, one successful Task/Run, exact total 19, Artifact/Evaluation completion, no Tool/MCP Events, no raw source/credential in SQLite, payload deletion, unchanged references, and cleanup `COMPLETED`.

## Windows live closure

The user-reported Windows execution passed all 21 checks with one source read, zero writes, no replay reread, one successful Task/Run, exact total 19, one Artifact, PASSED Evaluation, protected-payload deletion, unchanged references, and cleanup `COMPLETED`. See `docs/evidence/STEP025_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.

The next code-audited gap is case breadth, not another integration: only one canonical replenishment input/output pack and one Evaluation case exist.
