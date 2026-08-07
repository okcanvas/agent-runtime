# OR-ISSUE-036 — STEP081 consolidated restructuring execution overrode per-wave validation sequencing

## Status

```text
USER_RATIFIED_EXECUTION_OVERRIDE_RECORDED
FINAL_CUMULATIVE_DETERMINISTIC_VALIDATION_PASSED
WINDOWS_LIVE_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact conflict

The ratified architecture constitution's `MIG-001` and `MIG-009` prescribe separate STEP waves and independent full validation for each bounded wave. During the restructuring, the user issued a later binding instruction to complete the planned structural reorganization first, avoid intermediate full suites, and run deterministic/regression/packaging/Fresh-ZIP/Windows validation after the restructuring was complete.

## Impact

The final tree contains the cumulative root move, Client/Protocol/Transport/Application/Adapter separation, compatibility layer and RuntimeInfo split under one STEP081 identity. Intermediate wave ZIPs and independent full-regression evidence do not exist and must not be fabricated after the fact.

## Decision

The later user instruction is recorded as a one-STEP execution-sequencing override, not as an architecture-boundary relaxation. All dependency, authority, security, event-truth, compatibility, packaging and runtime-disabled WebSocket clauses remain fully enforced. The candidate cannot be promoted while Windows live validation remains pending.

## Compensating controls

- exact STEP080A product baseline inventory and 100% changed-path registration;
- executable relocation manifest for every legacy Python/resource path;
- 38/38 static architecture Gate;
- 899/899 full Python regression with bounded checkpoints;
- 14/14 Node tests, Reference 4/4, direct imports 0 and npm pack;
- 16/16 wheel/editable/package-data validation;
- complete Fresh-ZIP rerun of the same validations;
- 301 compatibility aliases with zero missing targets;
- no official accepted-baseline promotion before Windows live 73/73.

## Recurrence-prevention gate

Future restructuring must either follow the constitution's bounded STEP waves or record an explicit user-ratified sequencing decision before code movement. Compliance validation requires this issue and `docs/governance/STEP081_CONSOLIDATED_RESTRUCTURING_EXECUTION_OVERRIDE.md` to remain present.
