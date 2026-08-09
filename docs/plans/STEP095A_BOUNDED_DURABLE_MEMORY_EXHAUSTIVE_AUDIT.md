# STEP095A — Bounded Durable Memory Exhaustive Audit

Status: READ_ONLY_AUDIT_PREPARED_NO_PRODUCT_MEMORY_IMPLEMENTATION
Current Runtime baseline audited: STEP094R2 / 2.78.2

## Purpose

Determine whether and how a durable user/task memory capability can be added without conflating three different state classes or weakening existing authorization/routing boundaries. This document records only facts verified in the current source and derives the smallest next contract questions from those facts.

## Code-verified current state

### 1. Session runtime is not a durable-memory abstraction

`okcanvas_agent_runtime/application/ports/stores.py::SessionRuntimePort` currently owns Session create/get/list, binding validation, active-Turn acquire/release, item counts, SDK Session access, compaction, rollback, key rotation and clear. It exposes `get_context_focus(session_id)` but no memory CRUD/query contract.

### 2. Session Context Focus is explicitly Session- and evidence-scoped

`SessionContextFocusRecord` contains:

```text
session_id
observation
source_run_id
source_turn_count
updated_at
```

It therefore records the last committed evidence-backed conversational focus for a Session. It is not a tenant/principal-owned long-term fact store.

### 3. Current Session persistence has no memory table

Both SQLite and PostgreSQL Session metadata schemas define the current Session lifecycle tables, key-rotation table and `product_session_context_focus`. No durable-memory table is present in those inspected schemas.

### 4. Storage topology has no memory owner

`StorageTopology` currently contains Product, submission/governed-admission, approval, ownership, evaluation, Session runtime and Artifact blob stores. There is no memory store/port member. In `postgresql-hybrid-v1`, the existing metadata adapters are required to share one PostgreSQL DSN; memory is not part of that validation today.

### 5. A Product identity boundary already exists

`ServicePrincipal` is transport-neutral and carries `token_id`, `tenant_id`, `principal_id` and roles. Service routes pass the authenticated principal into user-scoped Session, attachment, project-snapshot, submission and Run use cases. This is the current concrete identity boundary available for any future memory ownership design.

### 6. There is no current Service memory API

The inspected Service routes expose Sessions, local attachments, project snapshots, run submissions, approvals and Runs among other current capabilities. No durable-memory endpoint exists.

### 7. Retention mechanisms exist elsewhere, but are capability-specific

Current source contains explicit expiration/deletion concepts for attachments, project snapshots and protected submission payloads. Those patterns prove the Runtime already treats expiry/deletion as explicit lifecycle concerns, but they do not by themselves define memory retention semantics.

### 8. Session policy declares TTL but this audit does not treat that as durable-memory semantics

`SQLiteSessionPolicy` contains `ttl_seconds`. The existence of this policy field is not evidence that durable memory should inherit Session TTL or Session clear behavior. A dedicated memory lifecycle must be decided separately.

## Architectural separation required before implementation

```text
SDK Session history
  purpose: model conversation continuity
  owner/lifecycle: Product Session

Session Context Focus
  purpose: bounded recent entity/reference continuity
  provenance: committed Tool evidence + source Run/Turn
  owner/lifecycle: Product Session

Durable Memory (not implemented)
  purpose: intentionally retained user/task facts for future use
  owner/lifecycle: MUST be defined independently
```

A memory implementation that simply adds fields to `product_session_context_focus`, writes model prose into Session history, or relies on Session IDs as long-term ownership would violate these existing separations.

## STEP095A decisions that must be closed from code before Product changes

1. **Ownership scope** — determine which memory classes, if any, are tenant + principal scoped and whether task/conversation scoped memory is a separate type rather than a nullable owner field.
2. **Provenance contract** — define allowed sources (for example explicit user write vs normalized Tool/Run evidence) and the exact immutable source references/hashes required for persisted facts.
3. **Storage ownership** — decide whether memory joins the canonical `StorageTopology` and how SQLite/PostgreSQL implementations preserve equivalent semantics.
4. **Read authorization** — specify fail-closed tenant/principal scoping using current Service identity; stable reference or memory key must never replace authorization.
5. **Write admission** — define which Product boundary may create/update/delete memory and whether writes require explicit user intent or governed approval.
6. **Conflict semantics** — choose and prove a revision/version precondition for update/delete rather than last-writer-wins by accident.
7. **Retention** — specify explicit TTL/expiry/default retention and physical cleanup behavior independently of Session clear/compaction.
8. **Deletion** — specify logical vs physical deletion, auditability and whether deleted memory may ever re-enter model context.
9. **Sensitivity/privacy** — define bounded allowed content and rejected/redacted classes before persistence.
10. **Consumption policy** — keep memory non-authoritative for routing in the first implementation; define a later explicit evidence/policy gate before memory may affect routing or delegated capability selection.
11. **Model-authored content** — do not auto-persist arbitrary model prose in the foundation wave.
12. **Observability/evidence** — define deterministic tests proving tenant/principal isolation, provenance integrity, conflict handling, expiry/deletion and restart durability.

## Recommended next execution order

```text
STEP095A read-only source audit
  -> select exact existing lifecycle/concurrency patterns worth reusing
  -> write memory domain/port/storage/API contract
  -> static contract tests
  -> smallest SQLite implementation
  -> PostgreSQL parity
  -> Service authorization tests
  -> restart/retention/conflict tests
  -> only then consider model-context injection
```

## Explicitly out of scope for STEP095A

- no Runtime Product source modification;
- no new database table or migration;
- no memory API route;
- no model-context injection;
- no memory-driven routing;
- no automatic extraction or persistence of user/model conversation text.

This audit is intentionally conservative because the current code already has two state mechanisms—Session history and Session focus—that could otherwise be incorrectly repurposed as long-term memory.
