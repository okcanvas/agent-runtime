# STEP079 — Product-owned atomic Task/Run ownership transfer

## Identity

```text
STEP079_PRODUCT_OWNED_ATOMIC_TASK_RUN_OWNERSHIP_TRANSFER
version: 2.59.0
```

## Selected problem

Direct execution of the packaged STEP078 code reproduced OR-ISSUE-012. Product Task/Run rows and submission binding committed before the service route separately registered Task/Run ownership. An injected `task` owner registration failure returned HTTP 500 while retaining a real failed Task and Run with no service owner rows.

## Scope

- Add an immutable tenant/principal Task/Run ownership transition contract.
- Apply Task and Run owner creation/verification inside `SQLiteRunSubmissionStore.create_governed_task_run()` using the same `BEGIN IMMEDIATE` transaction.
- Apply the same transition to replayed/existing Task/Run IDs.
- Reject foreign existing Task/Run owners without owner replacement.
- Remove route-level post-commit Task/Run registration.
- Close STEP078 Windows live 53/53 in packaged evidence.
- Add deterministic, full-regression, fresh-ZIP and Windows live gates.

## Non-goals

- Tool Approval ownership atomicity.
- SQLite Session creation ownership atomicity.
- Distributed transactions or background garbage collection.
- Sandbox capability expansion.
- Selecting STEP080 before STEP079 Windows live acceptance.

## Windows live contract

STEP079 retains the complete STEP078 real `gpt-4.1`/Docker Sandbox flow and adds immediate assertions that the confirmed Task and Run each have exact `step079-tenant` / `step079-reviewer` owners. The initial check dictionary has 55 checks and API-key summary exclusion adds one, for exactly 56 checks.
