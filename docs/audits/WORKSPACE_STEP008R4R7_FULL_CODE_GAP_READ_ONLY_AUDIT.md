# WORKSPACE STEP008R4R7 — Full Code Gap READ_ONLY Audit

```text
Audit: WORKSPACE_STEP008R4R7_FULL_CODE_GAP_READ_ONLY_AUDIT
Mode: READ_ONLY
Source Workspace: WORKSPACE_STEP008R4R7_RUNTIME_STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Workspace Version: 0.8.4-r7
Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime Version: 2.75.0
Source ZIP SHA-256: a8cf80b010615d4f6c7616c8832cd156f8f2a35fdcaf41a279b5212a8c602a4f
Product source modifications: 0
Test execution: DEFERRED_BY_USER_UNTIL_MINIO_READY
Object Storage Live: DEFERRED
Audit date: 2026-08-07
```

## 1. Audit decision

The current STEP091D candidate is not rejected. Keep it as the current
`LOCAL_AND_FRESH_DETERMINISTIC_ACCEPTED / Promotion NOT_READY` candidate and leave the
real MinIO/S3-compatible live gate pending until a live server is prepared.

The audit did **not** find unfinished Product stubs such as Product-owned `TODO`, `FIXME`,
or `NotImplementedError`. The important remaining gaps are operational lifecycle,
network isolation, schema evolution, distributed execution, governed Product capabilities,
and documentation/source-of-truth consistency.

The most important new finding is that the next work should **not** automatically be
Artifact GC or a new Worker claim system.

Before production exposure there are three independent boundaries that need explicit closure:

1. current-document SOT alignment;
2. physical Admin/Service network isolation;
3. versioned PostgreSQL migration lifecycle.

Artifact GC should remain after the deferred Object Storage live acceptance because the
inventory/delete policy must be checked against real S3-compatible semantics.

## 2. Scope and method

The audit inventoried and statically parsed first-party source, tests, scripts, connectors,
clients, specifications, launchers and current planning/HANDOFF material. Third-party
`reference/upstream` trees and installed dependencies were excluded from Product deficiency
ownership.

No tests or live gates were executed in this audit because the user explicitly deferred
testing until MinIO is ready. Prior accepted evidence inside the source ZIP was treated as
historical evidence only.

### Static inventory

| Area | Files | Lines |
|---|---:|---:|
| First-party Python total | 972 | 163,857 |
| Runtime Product package | 348 | 46,969 |
| Runtime Protocols | 5 | 1,213 |
| Runtime Clients | 11 | 1,169 |
| Runtime tests | 252 | 31,347 |
| Runtime scripts | 258 | 67,877 |
| Workspace tests | 22 | 2,827 |
| Workspace scripts | 32 | 9,851 |
| Connector Python | 36 | 2,554 |

All 972 first-party Python files parsed with Python AST: **0 parse failures**.

Other first-party surfaces inventoried include 31 TypeScript files, 22 MJS files,
11 JavaScript files and 189 CMD launchers.

Product-owned `TODO/FIXME/NotImplementedError` stub findings: **0**.
Two `NotImplementedError` text matches occur only in tests that catch platform compatibility
exceptions.

## 3. Findings

### R7-AUDIT-001 — P0 corrective — Current document SOT conflict

**Classification:** current package defect.

Code/package evidence:

- root `PLANS.md` correctly identifies STEP008R4R7 / STEP091D / Runtime 2.75.0;
- `okcanvas-agent-runtime/PLANS.md` still identifies
  `STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE / 2.74.1`;
- the stale Runtime plan still says real PostgreSQL acceptance is pending even though the
  parent promoted baseline already accepted the real PostgreSQL gate 19/19;
- `docs/plans/OKCANVAS_AGENT_RUNTIME_PRODUCTIZATION_MASTER_PLAN.md` immediate backlog is
  still worded at the STEP091C era;
- `tests/test_workspace_step008r4r1_document_plan_and_storage_audit.py` does not include
  `okcanvas-agent-runtime/PLANS.md` in the current-document set;
- that test concatenates several documents and checks the current identity only in the
  combined text, so one correct document can hide another stale document.

**Impact:** a future chat that relies only on the ZIP can select the wrong baseline or reopen
an already accepted PostgreSQL gate.

**Closure:** synchronize current plans and issue registries, then make each current SOT file
individually prove the exact current Workspace/Runtime identity. Prefer one machine-readable
current-baseline registry that documentation and launchers consume.

This audit records the recurrence separately as
`WORKSPACE-ISSUE-040-RUNTIME-PLANS-SOT-DRIFT-AND-GATE-COVERAGE-GAP.md`.

---

### R7-AUDIT-002 — P0 pre-production — Admin and Service listener isolation

**Classification:** production boundary gap, not a default-local exploit claim.

Evidence:

- `bootstrap/application.py` constructs one `FastAPI` application;
- the same application registers the `/v1/service/**` Service router and the local Admin
  router;
- `transport/admin/rest/auth.py` authenticates Admin/Run-submitter requests with header
  secrets but does not enforce source address or listener ownership;
- `scripts/windows_entrypoint.py` defaults `OKCANVAS_API_HOST` to `127.0.0.1`, but accepts
  an arbitrary configured host and `validate_control_api_environment()` does not reject
  non-loopback binding;
- `docs/00-CONSTITUTION.md` states that credential-bearing operator traffic is loopback-only.

**Current safety:** the default `127.0.0.1` bind is loopback and therefore safe under the
default topology.

**Production gap:** when the Service API eventually binds to a network interface for
multi-user access, the same listener would also carry Admin routes. That conflicts with the
documented physical boundary.

**Recommended closure:** use separate listeners/processes: externally reachable Service API
and loopback-only Admin API. If a transitional single process is retained, enforce a
fail-closed Admin loopback rule and test an explicit non-loopback bind.

---

### R7-AUDIT-003 — P0 pre-production — No versioned PostgreSQL migration lifecycle

STEP091B3R1 proved the current PostgreSQL schema and transactions on a real server. It did
not prove upgrade of an existing production database.

Current PostgreSQL initialization uses patterns such as:

- `CREATE TABLE IF NOT EXISTS`;
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`;
- a version-1 `schema_migration` marker in the Product store.

No Alembic/Flyway/Liquibase integration or first-party ordered migration runner was found.

**Gap:** there is no current schema-version preflight, ordered upgrade plan, transactional
migration policy, rollback/restore requirement, or live upgrade gate from a retained older
schema.

**Recommended closure:** create a Product-owned migration catalog/runner and prove an
upgrade from a retained old schema on real PostgreSQL before claiming production DB
migration readiness.

---

### R7-AUDIT-004 — P1 pre-production — Static health, no readiness

`bootstrap/application.py:/healthz` returns `status=ok` and configuration metadata without
checking PostgreSQL, Artifact storage, Session storage or external connector readiness.

`ObjectStorageArtifactBlobStore.initialize()` is currently a no-op.

No Product `/readyz`, `/livez` or `/metrics` boundary was found.

**Recommended closure:** split liveness from readiness. Readiness should use bounded,
secret-safe dependency checks and clearly define which dependencies are mandatory for the
selected topology.

---

### R7-AUDIT-005 — P1 pre-production — Service credential lifecycle is static

`ServiceClientTokenRegistry` is a startup JSON registry whose entries contain exactly:

```text
token_id
token_sha256
tenant_id
principal_id
roles
```

There is no expiry, not-before, revocation timestamp, issuer/audience, key version or dynamic
reload lifecycle.

This is adequate as a foundation/local service boundary but not a complete production
credential lifecycle.

**Recommended closure:** prefer an external identity provider/OIDC-JWT validation boundary,
or introduce a durable revocation-aware rotating registry while retaining current
tenant/principal/role ownership checks.

---

### R7-AUDIT-006 — P1 after Object Storage live — Artifact orphan lifecycle

`ArtifactBlobStorePort` exposes:

```text
initialize / put / read / verify / delete / exists
```

It has no listing/inventory or object-age contract.

`ArtifactService.create_bytes()` performs an immediate compensating blob delete when metadata
registration raises. That covers the ordinary same-process failure, but a crash after `put`
or an unsuccessful compensation can still leave a blob.

The Product metadata port provides per-Run Artifact listing but no global storage-reference
inventory/removal lifecycle.

**Conclusion:** orphan inventory/GC cannot be implemented robustly through the existing
ports yet.

**Recommended closure after MinIO live:** bounded blob inventory, global metadata inventory,
age threshold, quarantine/recheck and idempotent deletion. Do not delete solely from one
scan.

---

### R7-AUDIT-007 — P1 after Object Storage live — Explicit S3 operational policy

The STEP091D client now correctly composes boto3/S3-compatible storage. Its Product-owned
settings currently cover endpoint URL, region and addressing style. Botocore configuration
explicitly owns S3v4 signing and addressing style.

The Product does **not** currently pin its own retry budget, connection/read timeout policy,
private CA/TLS policy or server-side-encryption requirement; it relies on SDK/environment
defaults for those areas.

This is not evidence that boto3 has no retries/timeouts. It means those behaviors are not
yet an OKCanvas-owned contract.

**Recommended closure:** keep this deferred until real MinIO live evidence exists, then
define only the operational controls actually required by observed deployment behavior.

---

### R7-AUDIT-008 — P2 scale — API/Worker split and lease renewal

This is **not** a green-field claim-system task.

The current submission ledger already contains durable claim owner/token/acquired/expires
and recovery state. However:

- `LocalExecutionCoordinator` explicitly describes itself as single-process;
- execution uses `asyncio.create_task`;
- lifecycle policy retains `recovery_mode=explicit-local-operator`;
- `distributed_worker_lease_enabled` is rejected;
- no heartbeat/lease-renewal path was found.

**Recommended closure:** extend the existing claim ledger with physical Worker ownership,
heartbeat/renewal, lost-worker reconciliation and forced Worker termination evidence.

---

### R7-AUDIT-009 — P2 scale — Distributed Session history / HA

PostgreSQL owns Session lifecycle metadata, active-Run fencing, counts and rotation
checkpoint. Actual SDK model conversation history intentionally remains encrypted local
SQLite.

That is a valid single-node boundary, but it prevents transparent Worker relocation unless a
sticky-session or distributed-history strategy is selected.

The current history policy deliberately does not silently TTL-expire history.

**Recommended closure:** select together with Worker/HA design, including retention and
recovery semantics.

---

### R7-AUDIT-010 — P2 product — Governed enterprise write is proposal-only

The router contains `enterprise-action-write-v1`, but the route is `proposal_only=True`.
Runtime capability facts also state that the Groupware Action Agent and Action MCP Server
are not implemented. The current Groupware Connector is read-only.

**Recommended closure:** follow Master Plan Phase 3 instead of mutating through the read
connector:

```text
separate Action Agent/MCP
write Command ledger
Approval bound to command hash
idempotency key + expected revision
Applied / No-change / Conflict / Rejected / Failed / Unknown
read-after-write reconciliation
```

---

### R7-AUDIT-011 — P2 product — Durable automation is proposal-only

The router recognizes `durable-automation-v1`, but returns
`durable-scheduler-not-configured` and `proposal_only=True`.

There is no Product automation registry/scheduler package in the audited runtime.

**Recommended closure:** a durable Automation registry creates governed Submissions; it
does not call Tools directly. Add schedule/condition-watch deduplication, restart-safe firing
and approval policy at execution time.

---

### R7-AUDIT-012 — P2 deployment — Real enterprise read deployment remains separate

Read-only Organization/Groupware connector foundations exist. Their local/Fake integration
does not itself prove actual enterprise private-network endpoints, production credentials,
OAuth refresh or provider-specific failure behavior.

This is primarily a deployment/live-acceptance gap rather than evidence that the existing
read architecture must be rewritten.

---

### R7-AUDIT-013 — P3 production — Operations and supply-chain closure

Master Plan Phase 9 remains materially open:

```text
metrics
backup / restore
key rotation
load / soak / failure injection
SBOM
dependency audit
tenant-escape / approval-substitution security tests
```

Repository inspection also found:

- no Product metrics/OpenTelemetry/Prometheus endpoint;
- no transitive Python lock file;
- `sh_setup.cmd` performs `pip install -e .`;
- most dependencies are bounded ranges rather than a full resolved lock;
- no repository-owned CI workflow, Dockerfile, Helm or Terraform deployment artifact was
  found.

Deployment may intentionally live outside this repository, so the last item is an ownership
gap, not proof that no deployment exists elsewhere.

---

### R7-AUDIT-014 — P3 maintainability — Concentrated orchestration and acceptance surface

Largest observed Product functions include approximately:

```text
generic_gateway.py run()                 1,650 lines
runtime_binding.py resolve()             1,034 lines
execution/service.py execute_prepared()    702 lines
generic_gateway.py execute()               507 lines
bootstrap/application.py create_app()      488 lines
submissions/service.py preflight()         453 lines
```

Runtime first-party scripts contain about 67,877 Python lines, compared with about 49,351
Python lines across Runtime Product + Protocols + Clients. The package also retains 189 CMD
launchers.

This does not justify an immediate rewrite. Existing failure history shows a more specific
first move: centralize current-step/package/launcher identity and validate it from one SOT.
Then split large functions only along already tested policy/adapter boundaries.

---

### R7-AUDIT-015 — P3 product — Skill V2 and Product Client remain planned

Master Plan still leaves:

- versioned Skill registry and bounded Skill search;
- Conversation/Run/Artifact/Approval/Automation Product UI;
- Service-API-only Product Web E2E.

The separate Product Service CLI exists; Runtime browser surfaces are development/operator
harnesses, not the intended final Product client.

---

### R7-AUDIT-016 — Explicit operating constraint — Model retry/fallback disabled

Current RuntimeInfo intentionally sets automatic model fallback false and both runner/provider
managed retry counts to zero.

This is **not classified as a bug**. It avoids unsafe replay before side-effect/reconciliation
rules are proven. It does mean transient provider failures are surfaced directly.

Do not enable retries until retryable categories, persisted attempts and side-effect safety
are explicit.

## 4. What should not be rebuilt

The audit found no code basis for the following rewrites:

1. **Do not create a second Worker claim ledger.** Claim/expiry/recovery state already exists.
2. **Do not replace PostgreSQL stores solely because migration tooling is absent.** Add a
   migration lifecycle around the accepted stores.
3. **Do not merge enterprise writes into the read-only Groupware connector.**
4. **Do not implement Artifact GC before real Object Storage semantics are accepted.**
5. **Do not enable model retry/fallback by default.**
6. **Do not rewrite large modules just because they are large.** Split only when an existing
   tested boundary can own the extracted responsibility.

## 5. Recommended order

### Immediate, MinIO-independent

```text
A. R7-AUDIT-001  Documentation SOT corrective closure
B. R7-AUDIT-002  Admin / Service physical network boundary
C. R7-AUDIT-003  Versioned PostgreSQL migration lifecycle
D. R7-AUDIT-004  Liveness / readiness boundary
E. R7-AUDIT-005  Production Service credential lifecycle
```

A is a small corrective wave and should be closed first because the user's ZIP-only
continuation rule depends on it.

B and C are both pre-production P0 boundaries. If no external Service listener will be
exposed yet, C can be implemented before B; before external exposure, B becomes mandatory.

### When MinIO is ready

```text
F. Current STEP091D real Object Storage Live gate
G. R7-AUDIT-006 Artifact orphan inventory / quarantine / GC
H. R7-AUDIT-007 Explicit Object Storage operational policy where live evidence requires it
```

### Product/distributed roadmap

```text
I.  Governed low-risk enterprise write
J.  Durable automation
K.  API/Worker physical split + heartbeat/lease renewal
L.  Distributed Session/HA
M.  Production metrics/backup/load/SBOM/security
N.  Product Client + Skill V2
```

## 6. Current gate status

No current acceptance state was changed by this audit.

```text
STEP008R4R7 / STEP091D Local/Fresh deterministic: retained
Windows R7 deterministic: not changed by this audit
Windows R7 Live OpenAI: not changed by this audit
Real Object Storage Live: DEFERRED until MinIO is prepared
Promotion: NOT_READY
```

No test result is claimed for this READ_ONLY audit.

## 7. ZIP-only continuation rule

When continuing from the audit bundle:

1. treat the nested original STEP008R4R7 ZIP as immutable Product source;
2. verify its SHA-256 is `a8cf80b010615d4f6c7616c8832cd156f8f2a35fdcaf41a279b5212a8c602a4f`;
3. read this audit before selecting a new Step;
4. do not trust the stale `okcanvas-agent-runtime/PLANS.md` current baseline until
   R7-AUDIT-001 is corrected;
5. do not infer that Object Storage live acceptance passed;
6. keep all Product modifications at zero until a specific follow-up Step is selected.
