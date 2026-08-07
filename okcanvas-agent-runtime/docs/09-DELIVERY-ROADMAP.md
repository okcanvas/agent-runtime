# Delivery Roadmap

## Delivery principles

- Build one durable product boundary at a time.
- Reuse the inspected SDK instead of reproducing it.
- Keep Codex as an optional vertical, not the architecture spine.
- Prefer a local modular monolith until separation is justified.
- Every live capability requires a deterministic acceptance case and Evidence.

## Track A — Core product runtime (primary)

### STEP005 — Core Task, Run, Event and Artifact Store

SQLite and repository ports, with no HTTP and no new Agent capability.

Acceptance:

- legal state transitions;
- append-only per-Run event sequence;
- atomic Run + terminal event transaction;
- artifact SHA and missing-file detection;
- restart persistence;
- concurrent sequence allocation test;
- no secret or raw API key persistence.

### STEP006 — Read-only Reference Catalog Service — COMPLETE

Use the supplied immutable reference as a bounded source of implementation evidence.

Acceptance:

- manifest and tree-hash verification;
- code-map-first lookup;
- path traversal and symlink escape rejection;
- exact file and line-range result;
- no upstream mutation;
- reference access recorded as canonical Run events and artifacts where appropriate.

### STEP007 — Generic Agent Execution Service — COMPLETE, LIVE ACCEPTED

Move beyond Codex-specific entrypoints without adding multiple Agents.

Acceptance:

- immutable Agent definition resolution;
- generic Runner start and resume;
- Session explicitly optional and separate from Task state;
- canonical event normalization;
- structured output and usage persistence;
- Tool policy deny by default.

### STEP008 — Control API and persisted SSE — IMPLEMENTED, ASGI ACCEPTED

FastAPI only after the store and event journal exist.

Acceptance:

- Task/Run read and create APIs;
- authenticated ownership boundary placeholder or local-admin-only mode;
- HTTP failure codes match execution outcome;
- SSE cursor resumes from persisted event sequence;
- heartbeat, cancellation and terminal event behavior;
- no SDK event classes in the public contract.

### STEP009A — First read-only MCP integration — COMPLETE, LIVE ACCEPTED

Start with reference/project context, not ERP writes.

Acceptance:

- explicit server allowlist;
- Tool schema and result limits;
- timeout and reconnect behavior;
- read-only policy evidence;
- Tool calls normalized into Run events.

### STEP010 — Evaluation and regression service — COMPLETE

Turn fixture acceptance into repeatable quality measurement.

Acceptance:

- case manifests;
- expected and forbidden outcomes;
- cost, latency and tool-call totals;
- result comparison across model/config versions;
- no automatic product gate from model self-evaluation alone.

## Track B — Codex capability (optional parallel track)

### STEP004 live acceptance

Run when convenient. It proves persisted SDK interruption/resume, but is not required to begin STEP005.

### Later Codex steps

Only after the core store and project ownership policy:

- external project registration;
- workspace lease and snapshot;
- language-specific validator presets;
- optional Windows worker;
- patch review and operator apply/export.

Do not add another generic Sandbox coding stack while Codex remains adequate.

## Track C — durable and business integrations (later)

- PostgreSQL persistence and separated worker leases;
- object artifact storage;
- organization/tenant authorization;
- PlanVM MCP for approved deterministic execution;
- Temporal evaluation only when measured long-running recovery needs justify it;
- compiled frontend migration only when measured console complexity justifies it.

### STEP011 — Agent definition and evaluation catalog API — COMPLETE

Expose read-only catalogs and evaluation history through the existing local-admin API.

Acceptance:

- authenticated definition/case/history access;
- no instruction text or filesystem path disclosure;
- bounded history filters and pagination;
- deterministic comparison;
- read requests do not mutate evaluation storage.

### STEP012 — Recorded Run evaluation application service — COMPLETE

Connect completed Product Runs directly to deterministic Evaluation.

Acceptance:

- successful Task and Run required;
- canonical Event and Usage reconstruction;
- final-output Artifact integrity and output-contract validation;
- Agent definition ID/version/SHA verification;
- authenticated API and CLI;
- no model call and no raw output in Evaluation storage.

## Immediate next action

STEP028 is Windows live accepted. STEP029 is implemented and deterministically accepted. Run `sh_run_step029_acceptance.cmd` on Windows and close strict external scalar typing before selecting another capability. The general Operations Console remains read-only. Inventory writes, purchase-order creation, remote source origins, additional business Agents, browser mutation, tenant authorization, and distributed execution remain deferred.

### STEP012A — Windows Evaluation SQLite handle release — COMPLETE

Explicitly closes every operation-scoped Evaluation SQLite connection after commit or rollback.

### STEP013 — Evaluation Suite and Baseline Service — COMPLETE

Versioned deterministic Suites, explicit immutable Baselines, and informational regression comparison.

### STEP014 — Acceptance Workspace and Evidence Lifecycle — COMPLETE, WINDOWS ACCEPTED

Standardized resource close, compact Evidence export, PASS cleanup, and failure preservation.

### STEP015–016 — Read-only Operations Console and persisted live view — IMPLEMENTED, DETERMINISTIC ACCEPTED

Same-origin observation surfaces over durable Product state and persisted SSE. Browser live acceptance remains pending.

### STEP017 — Run submission and approval boundary — COMPLETE, WINDOWS ACCEPTED

Separate submit authority, exact request fingerprint confirmation, idempotency, and direct Run API deny-by-default.

### STEP018–019 — Governed read-only execution, claim recovery, and payload retention — IMPLEMENTED, DETERMINISTIC ACCEPTED

AES-256-GCM protected input, atomic Task/Run binding, generation fencing, bounded stale pre-start recovery, and explicit retention.

### STEP020 — Governed local Tool approval interruption and resume — COMPLETE, WINDOWS LIVE ACCEPTED

Official SDK `needs_approval`, encrypted RunState, separate-process approve/reject resume, and exactly-one Tool entry. Installed-SDK Windows approve/reject is accepted.

### STEP021 — Read-only local Approval Inbox — COMPLETE, WINDOWS ACCEPTED

Bounded safe approval metadata in API and read-only console.

### STEP022 — Windows live-acceptance closure harness — COMPLETE

One command closes STEP021 Windows acceptance and STEP020 installed-SDK approve/reject evidence.

### STEP023 — Minimal local approval operator CLI — COMPLETE, WINDOWS ACCEPTED

Loopback-only CLI for safe Inbox listing and one-at-a-time approve/reject. Both CLI and server require the exact decision confirmation. No browser mutation surface is added.


### STEP024–024B — Store replenishment review Agent vertical slice — WINDOWS LIVE ACCEPTED

First commerce-shaped read-only Agent using the existing governed submission path, a
business-specific structured output contract, an immutable case pack, deterministic invalid-final-
output recovery, and deterministic recorded-Run evaluation. The accepted Windows run produced exact
12/7/0 quantities, one verified Artifact, a PASSED Evaluation, payload deletion, and cleanup
`COMPLETED`.

### STEP025 — Governed read-only commerce snapshot ingress — WINDOWS LIVE ACCEPTED

One product-owned loopback HTTP GET acquires and validates the complete snapshot before the existing
protected-payload fingerprint and exact confirmation. Adapter identity, source-request hash, and
snapshot hash are bound; idempotent replay does not read again. The Windows run passed all 21 checks with one read, zero writes, total 19, and cleanup `COMPLETED`.

### STEP026 — Store replenishment multi-case product acceptance — WINDOWS LIVE ACCEPTED

Four valid canonical snapshots cover shortage, all-covered READY, equal-quantity tie ordering, and single-shortage behavior. One duplicate-SKU source response fails before persistence. Deterministic acceptance passed 22/22 with five reads, zero writes, four Artifacts, four PASSED Evaluations, successful payload deletion, and cleanup `COMPLETED`. The Windows run passed all 22 checks with the same counts, exact results, invalid-source rejection, and cleanup `COMPLETED`.


### STEP027 — Commerce snapshot ingress failure-matrix product acceptance — WINDOWS LIVE ACCEPTED

Fourteen existing source, authentication, response, transport, configuration, request, and adapter failure branches are exercised through the Control API. Deterministic acceptance passed 24/24 with nine loopback reads, zero redirect follows, one transport attempt, zero writes, zero Product/Evaluation/Artifact/payload state, zero model calls, unchanged References, and cleanup `COMPLETED`. The Windows rerun passed all 24 checks with the same exact failure contracts, zero Product/model state, and cleanup `COMPLETED`.


### STEP028 — Commerce snapshot identity consistency — WINDOWS LIVE ACCEPTED

The returned `snapshot_id` must exactly equal the normalized requested `snapshot_key`. A mismatch returns non-retryable `COMMERCE_SNAPSHOT_IDENTITY_MISMATCH` before Product persistence, protected payload, Artifact/Evaluation, or model execution. Deterministic acceptance passed 15/15 with one loopback read, zero writes, zero state, unchanged References, and cleanup `COMPLETED`. The Windows rerun passed the same 15 checks and is closed.


### STEP029 — Commerce snapshot strict scalar types — IMPLEMENTED, DETERMINISTIC ACCEPTED

External inventory quantities are now type-exact JSON integers. Numeric strings, booleans, and integral floats are rejected before Product persistence or model execution. Deterministic acceptance passed 18/18 across four coercion cases with four reads, zero writes, zero Product/model state, unchanged References, and cleanup `COMPLETED`. Windows rerun is pending.
## Sub-Agent isolation note after STEP036B

- Agent definition isolation and invocation identity are P0 requirements.
- Physical workspace/session allocation is conditional on filesystem capability.
- Every file-capable root or child invocation receives a separate writable workspace.
- Shared source is transferred as an immutable snapshot or explicit read-only mount.
- General Sandbox execution remains an independent later track, not a prerequisite for language-only Handoff.

