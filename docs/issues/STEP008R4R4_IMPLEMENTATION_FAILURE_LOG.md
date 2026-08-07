# STEP008R4R4 Implementation Failure Log

## 1. Runtime partition summary path required current STEP091C evidence

Workspace integration must consume `STEP091C_FULL_RUNTIME_TEST_PARTITIONS.json`, not the retained
STEP091B2 full-suite summary. Parent evidence remains available only for retained PostgreSQL checks.

## 2. Current identity tests must distinguish historical STEP091B2 evidence from current STEP091C identity

Historical PostgreSQL tests continue to read STEP091B2 evidence, while catalog/HANDOFF assertions use
the current STEP008R4R4 / STEP091C identity.

## 3. Current stage-label test and storage lineage documentation were stale

The current Workspace runner correctly emits `[WORKSPACE STEP008R4R4]`, while one retained test still expected R4R3. The test now follows the current runner identity. Current HANDOFF also records the retained STEP091B1 → STEP091B2 → STEP091C storage lineage so ZIP-only continuation does not lose the transaction-ownership foundation.

## 4. Bounded command windows interrupted complete gates without product failure

The first Runtime Fresh gate was terminated during architecture validation, and the first Workspace gate was terminated during Connector→Example E2E. Both were rerun as background processes and completed successfully. A supplied focused evidence file is accepted only after state/exit validation, while the Runtime gate still executes architecture, launcher, compile and all other checks and binds evidence to the current source snapshot digest.

## 5. Current mutable acceptance evidence exclusion was missing

`WORKSPACE_STEP008R4R4_ACCEPTANCE.json` was added to the Workspace mutable-evidence exclusion set so a redirected/current acceptance result cannot create manifest or package drift.
