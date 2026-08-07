# STEP091B3R1 Real PostgreSQL Live Acceptance Gate

```text
STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE
Version: 2.74.1
Parent: STEP091B3 / 2.74.0
```

## Objective

Close the missing verification boundary between deterministic PostgreSQL adapter
contracts and a real PostgreSQL server without changing Product behavior or making
PostgreSQL the default topology.

STEP091B3 implemented the adapter and topology contracts but explicitly did not run a
real PostgreSQL server. STEP091B3R1 adds the dedicated gate needed to verify those
contracts against PostgreSQL itself.

## Safety boundary

The live gate is intentionally fail-closed.

```text
Required DSN env:         OKCANVAS_POSTGRESQL_LIVE_DSN
Required confirmation:    OKCANVAS_POSTGRESQL_LIVE_CONFIRM
Exact confirmation value: CREATE_AND_DROP_ISOLATED_TEST_SCHEMA
Schema prefix:            okcanvas_step091b3r1_
```

The gate:

1. rejects a missing or invalid DSN;
2. rejects a missing or non-exact destructive confirmation;
3. creates one randomized isolated schema;
4. forces `search_path` to that schema for every topology connection;
5. performs all live verification in that schema;
6. drops the schema from a `finally` block;
7. never persists the raw DSN, database name or database user.

## Live contracts

```text
Connection and DDL
- actual PostgreSQL server connection
- expected topology tables created in the isolated schema
- all PostgreSQL metadata stores expose one DSN digest

Atomicity and concurrency
- concurrent governed admission converges to one Task/Run
- injected ownership failure rolls back Task/Run/Event/Submission atomically
- concurrent Run Event append produces contiguous unique sequence numbers

Approval and Evaluation
- Tool Approval state machine persists
- execution reservation/resume fence permits one execution
- Evaluation result round-trip persists

Session and restart
- concurrent active-Run ownership is row-lock fenced
- Session metadata survives service recreation
- Product Task/Run rows survive store recreation
- SDK Session history remains encrypted local SQLite

Compatibility and evidence
- sqlite-local-v1 remains the default
- output contains hashes rather than credentials or identifiers
- isolated schema cleanup succeeds
```

## Source boundary reviewed before implementation

The PostgreSQL stores inherit semantic methods from retained SQLite store classes while
replacing connection, DDL and SQL translation boundaries. Therefore a connection-only
smoke test was rejected. The live gate executes inherited high-risk paths—admission,
events, Approval, Evaluation and Session metadata—against PostgreSQL to expose SQL,
type, transaction and locking incompatibilities.

## Deterministic acceptance

```text
STEP091B3R1 deterministic       21/21 PASSED
Architecture                    40/40 PASSED
Focused regression              42/42 PASSED
Full Runtime test files         250/250
Full Runtime tests              1,044/1,044 PASSED
Partitions                      18/18 exact
Failed / skipped                0 / 0
Missing / duplicate files       0 / 0
```

## Real-server status

```text
Real PostgreSQL server          NOT RUN
psycopg in current environment  UNAVAILABLE
PostgreSQL client/server tools  UNAVAILABLE
Production database             NOT USED
```

This status does not prove or disprove live compatibility. It proves only that the
dedicated live gate is implemented and deterministically validated.

## Windows command

```text
set OKCANVAS_POSTGRESQL_LIVE_DSN=postgresql://...
set OKCANVAS_POSTGRESQL_LIVE_CONFIRM=CREATE_AND_DROP_ISOLATED_TEST_SCHEMA
sh_run_step091b3r1_postgresql_live_acceptance.cmd
```

Run only against a disposable or dedicated non-production database whose role can
create and drop schemas.

## Not implemented or claimed

- PostgreSQL production-live acceptance
- Production migration execution
- Distributed Session history
- Real Object Storage acceptance
- API/Worker physical split
- Distributed claim or lease
