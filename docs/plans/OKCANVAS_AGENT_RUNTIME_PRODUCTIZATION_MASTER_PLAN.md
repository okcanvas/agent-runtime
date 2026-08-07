# OKCanvas Agent Runtime Productization Master Plan

```text
Current Workspace: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Workspace Version: 0.8.4-r7a1
Current Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime Version: 2.75.0
State: CURRENT_PLAN_ALIGNED_BY_STEP008R4R7A1
Promotion: NOT_READY
MinIO/Object Storage Live: DEFERRED_BY_USER
```

## Principle

Audit current code first, preserve existing Product semantics, and implement the smallest closed
boundary. Historical evidence keeps its original identity. Current package identity is read from
`specs/workspace/current-baseline.json` and current documents are validated independently.

## Phase 0 — Current package and documentation closure

- STEP091A Product storage READ_ONLY audit — complete.
- STEP091B1 typed persistence ports / transaction ownership — complete.
- STEP091B2 PostgreSQL Product + Submission atomic store — complete.
- STEP091C Artifact blob store / SDK-neutral Object Storage boundary — complete.
- STEP091B3 Approval / Evaluation / Session metadata PostgreSQL adapters — complete.
- STEP091B3R1 real PostgreSQL isolated-schema acceptance — 19/19 accepted on parent promoted R6.
- STEP091D Object Storage deployment composition + live gate implementation — complete; real
  MinIO/S3-compatible live execution pending.
- STEP008R4R7A current-document SOT alignment + per-file identity gate — retained.
- STEP008R4R7A1 Git repository hygiene + retained Runtime dist tracking — implemented/static-validated;
  tests remain deferred by user until MinIO is prepared.

## Phase 1 — Pre-production network boundary

Physically separate externally reachable Service API traffic from loopback-only Admin/operator
traffic. Do not rely on one externally bound listener carrying both route families.

Exit: non-loopback Service bind cannot expose Admin routes; Admin listener is independently
loopback-owned and regression covered.

## Phase 2 — Versioned PostgreSQL schema evolution

Add a Product-owned ordered migration catalog/runner, schema-version preflight, upgrade policy,
transaction/backup/restore rules and retained-old-schema upgrade evidence.

Exit: an existing retained PostgreSQL schema upgrades deterministically to current without relying
only on `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` initialization.

## Phase 3 — Dependency-aware service readiness

Split liveness from readiness. Readiness must use bounded, secret-safe checks for dependencies
required by the selected topology (database, Artifact storage, Session ownership and required
connectors).

## Phase 4 — Service credential lifecycle

Move beyond startup-static bearer JSON toward expiry/revocation/rotation or an external OIDC/JWT
identity boundary while retaining tenant/principal/role authorization semantics.

## Phase 5 — Object Storage lifecycle, after real MinIO/S3 live acceptance

- Execute STEP091D isolated-prefix live gate against the prepared real server.
- Add bounded blob inventory and global metadata storage-reference inventory.
- Add age threshold, quarantine/recheck and idempotent orphan deletion.
- Pin only operational retry/timeout/TLS/encryption controls justified by live deployment evidence.

Exit: crashes/failed compensation cannot create permanently undiscoverable blobs and deletion is
never based on one unconfirmed scan.

## Phase 6 — API / Worker physical separation and HA

Reuse the existing durable claim owner/token/acquired/expires/recovery fields. Add physical Worker,
heartbeat/lease renewal, lost-Worker reconciliation and forced-termination acceptance. Then decide
distributed Session history versus explicit sticky ownership/recovery.

Exit: forced Worker loss recovers without duplicate execution.

## Phase 7 — Governed enterprise write

Implement separate action Agent/MCP credentials, durable Command ledger, hash-bound Approval,
idempotency/expected revision, unknown-outcome reconciliation and read-after-write verification.
Current `enterprise-action-write-v1` routing remains proposal-only until this boundary exists.

## Phase 8 — Durable Automation

Implement a restart-safe Automation registry/scheduler that creates governed Submissions with
schedule/condition dedupe and execution-time approval. Current `durable-automation-v1` routing
remains proposal-only until this boundary exists.

## Phase 9 — Product UI / Skill Platform / operations

After execution and production boundaries stabilize: versioned Skill registry/search, Product
Conversation/Run/Artifact/Approval/Automation UI, metrics/tracing, backup/restore, load/soak/failure
injection, dependency lock, SBOM/security audit and owned deployment automation.

## Immediate ordered backlog

```text
P0 STEP008R4R7A current-document SOT correction      IMPLEMENTED / TESTS DEFERRED
P0 Admin / Service listener physical isolation       NEXT MINIO-INDEPENDENT CANDIDATE
P0 Versioned PostgreSQL migration lifecycle          AFTER NETWORK BOUNDARY
P1 Dependency-aware livez/readyz                     OPEN
P1 Service credential lifecycle                      OPEN
P1 STEP091D real MinIO/Object Storage live           DEFERRED UNTIL MINIO READY
P1 Artifact inventory/quarantine/GC                  AFTER OBJECT STORAGE LIVE
P2 Physical Worker + heartbeat/lease renewal         OPEN LATER
P2 Distributed Session history / HA                  OPEN LATER
P2 Governed Groupware write                          PROPOSAL_ONLY TODAY
P2 Durable Automation                                PROPOSAL_ONLY TODAY
P3 Product UI / Skill V2 / production operations     OPEN LATER
```

## Guardrails

- never infer production readiness from deterministic adapters alone;
- never rewrite historical evidence to the newest current Step;
- never build a second Worker claim system when durable claim state already exists;
- never delete Artifact blobs from a single unconfirmed orphan scan;
- never expose credential-bearing Admin/operator routes merely because the Service listener must
  become externally reachable;
- do not run MinIO/Object Storage tests until the user-provided MinIO environment is ready.
