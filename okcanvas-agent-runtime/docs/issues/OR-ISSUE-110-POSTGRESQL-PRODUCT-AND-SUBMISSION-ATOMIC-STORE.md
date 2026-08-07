# OR-ISSUE-110 — PostgreSQL Product and Submission Atomic Store

## Proven problem

STEP091A proved that direct PostgreSQL CRUD adapters would break governed admission because Product
Task/Run/Event creation and Submission binding must share one transaction owner. STEP091B1 exposed
that ownership through typed ports.

## Closure

STEP091B2 adds a PostgreSQL hybrid topology that places Product state, Submission state and service
Task/Run ownership on one DSN. Governed admission remains one transaction. Submission transitions use
row locks, idempotency registration uses a transaction advisory lock, and Event sequence allocation
locks the owning Run. SQLite remains the default.

## Remaining limitation

The build environment had no PostgreSQL server or psycopg package. Deterministic adapter and SQL
contract tests passed, but PostgreSQL-live acceptance remains mandatory before promotion.
