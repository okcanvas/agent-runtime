# STEP081 consolidated restructuring execution override

## Authority and scope

The user explicitly directed that the complete planned structure reorganization be performed before running the full deterministic, regression, packaging, Fresh-ZIP and Windows suites. This decision supersedes only the per-wave validation timing in `MIG-001` and `MIG-009` for the STEP081 candidate.

It does **not** relax any architectural boundary. In particular, it does not permit Transport→Store/Coordinator, Client→Runtime, Protocol→Runtime, Application→concrete Adapter, Agent→Transport framework, WebSocket authority escalation, duplicate package roots, stale source paths, or incomplete compatibility coverage.

## Evidence and promotion boundary

The cumulative candidate is acceptable for deterministic packaging only after all final cumulative controls pass. Promotion to the official accepted baseline remains prohibited until fresh Windows execution completes the registered 73-check live contract.

```text
execution mode: USER_RATIFIED_CONSOLIDATED_CANDIDATE
intermediate full-suite checkpoints: NOT CREATED
final cumulative deterministic validation: REQUIRED_AND_PASSED
fresh ZIP validation: REQUIRED_AND_PASSED
Windows live promotion gate: PENDING_EXTERNAL
```

## Rollback

The immutable STEP080A ZIP with SHA-256 `11a554e6a0fda3e728002ce915e9b3729622928919f30c5d30390814d2d29702` remains the rollback and reconstruction baseline until STEP081 Windows live acceptance is supplied.
