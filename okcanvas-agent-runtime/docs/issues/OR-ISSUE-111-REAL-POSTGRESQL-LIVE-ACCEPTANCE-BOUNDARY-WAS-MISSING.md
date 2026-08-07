# OR-ISSUE-111 — Real PostgreSQL live acceptance boundary was missing

## Proven problem

STEP091B2 and STEP091B3 supplied PostgreSQL adapters and deterministic SQL/transaction
contracts, but no dedicated real-server gate executed the inherited high-risk Product,
Approval, Evaluation and Session paths against PostgreSQL.

A connection-only test would be insufficient because the PostgreSQL adapters retain
semantic methods inherited from SQLite stores while replacing connection, SQL
translation, DDL, transaction and row-lock behavior.

## Risk

Deterministic tests could remain green while a real server rejected SQL syntax or type
bindings, or while transaction rollback, row locks, concurrent admission, Event
sequence allocation, Approval resume fencing or Session active-Run fencing behaved
differently.

## Closure

STEP091B3R1 adds an operator-confirmed isolated-schema live gate covering all of those
paths. It hashes database identity fields, never records the raw DSN, and drops the
schema in `finally`.

## Remaining limitation

The current environment has neither PostgreSQL tools nor `psycopg`, so the live gate
has not been executed. PostgreSQL production readiness remains explicitly unclaimed.
