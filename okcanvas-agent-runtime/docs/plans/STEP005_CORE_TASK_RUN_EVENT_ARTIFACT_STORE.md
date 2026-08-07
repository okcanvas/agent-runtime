# STEP005_CORE_TASK_RUN_EVENT_ARTIFACT_STORE

## Objective

Implement the first durable OKCanvas product-state boundary without adding HTTP, MCP, Codex capability, or another Agent.

## Current code evidence

- the Agents SDK owns execution mechanics, Session, RunState, streaming, tracing, and MCP;
- STEP002 and STEP003 proved Codex-specific execution slices;
- product Task, Run, Event, and Artifact state was previously scattered across local JSON Evidence and was not represented by one durable store;
- the reference demos do not provide production Task ownership, append-only events, artifact integrity, or product-state recovery.

## Scope

- standard-library SQLite store;
- migration version table;
- repository Protocol;
- Task and Run records and legal transitions;
- append-only ordered Run events;
- atomic Run transition plus event insertion;
- Artifact path, size and SHA-256 metadata;
- restart persistence;
- concurrent event sequence allocation;
- deterministic local acceptance script.

## Non-scope

- REST/SSE and authentication;
- user, tenant, project and organization models;
- SDK Session persistence;
- approval migration from STEP004 JSON to SQLite;
- PostgreSQL;
- worker queue and leases;
- Validation table;
- Codex, MCP, PlanVM, Temporal, UI or external projects.

## Contracts

- `src/okcanvas_agent_runtime/product/` owns product models, transitions, ports and errors;
- `src/okcanvas_agent_runtime/persistence/sqlite_store.py` owns the SQLite adapter;
- task input is represented by SHA-256 and optional protected payload reference, never a raw secret-bearing input field;
- event payload JSON is canonicalized and hashed;
- an Artifact is valid only when its file exists and current size and SHA-256 match stored metadata.

## Acceptance criteria

1. migration initialization is idempotent;
2. Task and Run state survives a new store instance;
3. illegal Task and Run transitions fail closed;
4. a Run transition and its Event commit or roll back together;
5. concurrent Event appends allocate one unique monotonic sequence per Run;
6. event payload hashes are deterministic;
7. Artifact missing and modified files are detected;
8. a sentinel API key supplied only as hashed input is absent from database bytes;
9. `scripts/verify_core_store.py` completes with `state=PASSED`;
10. all previous STEP regressions and reference integrity remain green.

## Failure and recovery

- SQLite uses foreign keys, WAL and busy timeout;
- each mutating operation uses an explicit transaction where multiple records must agree;
- a failed transition leaves the previous state and event list intact;
- no automatic database repair is claimed;
- migration version 1 is append-only and later schema change must add a new migration.
