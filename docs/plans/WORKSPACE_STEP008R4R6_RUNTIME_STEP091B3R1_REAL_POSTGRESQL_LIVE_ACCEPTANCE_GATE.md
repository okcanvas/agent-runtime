# WORKSPACE STEP008R4R6 Runtime STEP091B3R1 Real PostgreSQL Live Acceptance Gate

```text
Workspace: WORKSPACE_STEP008R4R6_RUNTIME_STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE
Workspace version: 0.8.4-r6
Runtime: STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE
Runtime version: 2.74.1
Parent Workspace: STEP008R4R5 / 0.8.4-r5
Parent Runtime: STEP091B3 / 2.74.0
```

## Objective

Integrate the Runtime's dedicated real PostgreSQL gate into the Workspace without
claiming a live pass and without changing the accepted Organization Context flow.

## Workspace contract additions

```text
postgresql_live_gate_implemented = true
postgresql_live_gate = real-postgresql-isolated-schema-v1
postgresql_live_dsn_env = OKCANVAS_POSTGRESQL_LIVE_DSN
postgresql_live_confirmation_env = OKCANVAS_POSTGRESQL_LIVE_CONFIRM
postgresql_live_confirmation_value = CREATE_AND_DROP_ISOLATED_TEST_SCHEMA
postgresql_live_schema_prefix = okcanvas_step091b3r1_
postgresql_live_accepted = false
```

## Retained boundaries

- `sqlite-local-v1` is still the default topology.
- PostgreSQL is still explicit opt-in.
- STEP091B3 metadata semantics are unchanged.
- SDK Session history remains encrypted local SQLite.
- STEP091C Artifact binary storage boundary remains unchanged.
- Organization Context Router/Agent/Skill/MCP/Connector/Example sources remain unchanged.
- Parent STEP008R4 Windows Live OpenAI 29/29 acceptance remains historical evidence,
  not a current-step live claim.

## Deterministic acceptance requirements

- current Workspace/Runtime identity exact;
- fresh Runtime STEP091B3R1 21/21 execution with source unchanged;
- real PostgreSQL live-gate source and contract exact;
- retained STEP091B1/B2/C/B3 storage contracts exact;
- Runtime full regression 250 files / 1,044 tests / 18 exact partitions;
- Workspace unit tests pass;
- Connector 11/11, Example 19/19, integration 17/17 pass;
- Workspace manifest drift is zero;
- no source project mutates during acceptance.

## Promotion boundary

`postgresql_live_accepted` remains false until the dedicated Runtime CMD is run against
a real non-production PostgreSQL database and its external evidence passes. Local/Fresh
deterministic acceptance alone cannot promote PostgreSQL production readiness.
