# WORKSPACE STEP008R4R2 — Runtime STEP091B1 Typed Persistence Ports and Transaction Ownership

```text
Workspace: WORKSPACE_STEP008R4R2_RUNTIME_STEP091B1_TYPED_PERSISTENCE_PORTS_AND_TRANSACTION_OWNERSHIP
Version: 0.8.4-r2
Runtime: STEP091B1_TYPED_PERSISTENCE_PORTS_AND_TRANSACTION_OWNERSHIP / 2.71.0
Parent Workspace: STEP008R4R1 / 0.8.4-r1
Parent Windows Product acceptance: STEP008R4 deterministic 25/25 and Live OpenAI 29/29 PASSED
```

## Purpose

Implement the first admitted boundary from the completed STEP091A read-only storage audit without introducing PostgreSQL, Object Storage, distributed Worker leasing, or new Product behavior.

## Exact implementation scope

1. Replace broad persistence Protocol signatures with explicit typed signatures.
2. Separate governed Task/Run/Event/Submission admission from the Submission ledger port.
3. Retain one SQLite transaction owner for atomic governed admission.
4. Introduce a validated storage topology bundle used by Bootstrap.
5. Remove concrete SQLite Session and Evaluation types from application contracts.
6. Add deterministic Runtime acceptance, launcher registry entries, full partitioned Runtime regression, and Workspace integration checks.

## Explicit non-goals

```text
PostgreSQL adapter
ArtifactBlobStorePort
Object Storage adapter
API/Worker physical separation
distributed lease/heartbeat
Organization Context Product semantic changes
Router/Agent/Skill/MCP changes
Connector or Example implementation changes
```

## Required invariants

- `SQLiteRunSubmissionStore` implements both `RunSubmissionStorePort` and `GovernedRunAdmissionPort`.
- The SQLite storage topology rejects different Submission and admission owners.
- Atomic governed admission continues to write Product Task, Run, Run Event and Submission binding in one SQLite transaction.
- Application services depend on ports, not SQLite concrete classes.
- Artifact filesystem semantics remain unchanged and explicitly deferred.
- PostgreSQL remains unimplemented and cannot be accidentally advertised.

## Acceptance

### Runtime

```text
STEP091B1 deterministic             25/25
Architecture                        40/40
Focused regression                  96/96
Full Runtime suite                  246/246 files
Full Runtime tests                  1,024/1,024
Partitions                          12/12 exact
```

### Workspace

- current Workspace and Runtime identity exact;
- Runtime fresh gate and source immutability;
- typed persistence and admission ownership checks;
- Connector 11/11;
- Example 19/19;
- Connector→Example 17/17;
- existing Organization Context Root/Child/MCP boundary retained;
- parent STEP008R4 Windows Live evidence retained;
- manifest drift zero;
- Fresh ZIP repeated validation.

## Promotion rule

Because Bootstrap and persistence dependency wiring changed, parent STEP008R4 Live evidence is retained as regression context but is not sufficient to promote R4R2. Formal R4R2 promotion requires:

```text
Windows deterministic R4R2 acceptance = PASSED
Windows Live OpenAI R4R2 acceptance = PASSED
```

## Next admitted step

```text
STEP091B2_POSTGRESQL_PRODUCT_AND_SUBMISSION_ATOMIC_STORE
```

The PostgreSQL implementation must preserve the exact governed admission transaction boundary proved here.
