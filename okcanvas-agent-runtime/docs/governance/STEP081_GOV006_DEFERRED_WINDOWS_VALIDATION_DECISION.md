# STEP081 GOV-006 deferred Windows validation decision

## Binding clause

`GOV-006` states that Product source movement must not be promoted as the official baseline before the required Windows live acceptance is closed.

## Verified evidence state

At STEP081 implementation time, the repository contains deterministic STEP080A evidence but no supplied Windows live evidence proving the pending 67/67 STEP080A contract. No Windows live result is inferred or fabricated.

## Decision

The user explicitly directed the structural reorganization to proceed before the deferred Windows rerun. Therefore:

```text
physical restructuring implementation: ALLOWED AS A CANDIDATE
static and deterministic validation: ALLOWED
candidate ZIP generation: ALLOWED
promotion to official accepted baseline: PROHIBITED
Windows live status: PENDING_EXTERNAL
```

This does not amend or weaken GOV-006. It distinguishes implementation of a reviewable candidate from promotion of that candidate as the accepted baseline.

## Closure condition

STEP081 may be promoted only after the applicable Windows launchers run from a fresh extracted ZIP with real dependencies and all required checks pass. Until then all HANDOFF, compliance, Acceptance, and package records must state Windows live pending.
