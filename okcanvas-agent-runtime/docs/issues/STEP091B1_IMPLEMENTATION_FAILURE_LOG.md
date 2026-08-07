# STEP091B1 Implementation Failure Log

## Purpose

Record implementation and packaging failures so the same mistakes are not repeated.

## F1 — Launcher registry required-record shape was guessed incorrectly

### Failure

`required_current_records` was temporarily written as path strings. The validator rejected it because
the v2 registry contract requires unique `{kind, mode}` objects.

### Correction

Restored the exact contract:

```json
[
  {"kind": "python-script", "mode": "DETERMINISTIC"},
  {"kind": "windows-launcher", "mode": "DETERMINISTIC"}
]
```

### Prevention

Read the registry validator before editing the registry. Do not infer JSON shape from field names.

## F2 — Bootstrap admission argument was inserted into the wrong service

### Failure

A broad text replacement temporarily passed `admission_store` to
`GovernedExecutionLifecycleService`, which does not own Product admission.

### Correction

Removed the argument from lifecycle service and passed it only to:

- `GovernedReadOnlyRunSubmissionService`;
- `GovernedLocalToolApprovalService`.

### Prevention

Patch constructor call sites by exact class block, then run focused API tests before broad regression.

## F3 — Application port imported Evaluation package through its eager facade

### Failure

The typed port imported `application.evaluation.models`; Python initialized the package facade first,
which imported evaluation application code back into the ports module and caused a circular import.

### Correction

Evaluation model imports are now guarded by `TYPE_CHECKING`; postponed annotations preserve the exact
contract without a runtime package cycle.

### Prevention

Application ports must not import eager facades that import application services. Use leaf modules
under `TYPE_CHECKING` for annotation-only dependencies.

## F4 — Current HANDOFF lost retained historical identifiers

### Failure

Full regression detected that the rewritten HANDOFF omitted retained public identifiers including
`document-review-v1`, Groupware external connector paths, Product Tool names, `reference-catalog`,
and `OR-ISSUE-091`.

### Correction

Added an explicit retained catalog and connector identifier section to the current HANDOFF.

### Prevention

Before replacing HANDOFF, search all tests that inspect it and carry forward stable public identifiers.

## F5 — Historical baseline tests froze the prior package filename

### Failure

Two retained tests correctly followed the current Step/version but still asserted the STEP090R1 ZIP
name.

### Correction

Updated only their current package-identity expectation to the STEP091B1 filename. Historical
STEP090R1 acceptance code remains unchanged.

### Prevention

When promoting a Runtime baseline, search separately for current Step, version, and package filename;
these are independent identity fields.

## F6 — Monolithic partition command exceeded the tool execution window

### Failure

The helper command that attempted to run all 12 partitions in one container call was interrupted by
the outer execution window even though completed partitions had passed.

### Correction

Resumed from per-partition JSON/log evidence, ran remaining partitions individually, and aggregated
only after all 12 exact assignments existed.

### Prevention

Use the partition runner as designed: one bounded partition per process, then aggregate. Never treat
an outer tool timeout as a Product test failure without inspecting partition evidence.
