# STEP008R4R7A — Current Document SOT Alignment and Per-File Identity Gate

```text
Workspace: WORKSPACE_STEP008R4R7A_CURRENT_DOCUMENT_SOT_ALIGNMENT_AND_PER_FILE_IDENTITY_GATE
Version: 0.8.4-r7a
Runtime retained: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE / 2.75.0
Parent Workspace: WORKSPACE_STEP008R4R7_RUNTIME_STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE / 0.8.4-r7
Source release SHA-256: a8cf80b010615d4f6c7616c8832cd156f8f2a35fdcaf41a279b5212a8c602a4f
Product Runtime source modifications: 0
Test execution: DEFERRED_BY_USER_UNTIL_MINIO_READY
Promotion: NOT_READY
```

## Problem

The R7 full-code READ_ONLY audit discovered `WORKSPACE-ISSUE-040`: root current plans were STEP091D,
but nested Runtime `PLANS.md` remained at STEP091B3R1 / 2.74.1 and reopened already accepted real
PostgreSQL work. The existing regression omitted nested Runtime PLANS and checked concatenated
documents, so a correct sibling could hide stale current state.

## Implementation

1. Add `specs/workspace/current-baseline.json` as the current Workspace/Runtime identity SOT.
2. Align seven current root/Runtime/Productization documents to one exact four-line marker block.
3. Add `scripts/current_workspace_baseline.py` and make current manifest/acceptance scripts derive
   Workspace identity from the SOT rather than duplicating it.
4. Add `scripts/validate_current_document_sot.py` to validate every current document independently.
5. Add a regression that deliberately stales nested Runtime PLANS and requires validator failure.
6. Preserve all historical R7/R6/Runtime evidence without replacing its historical identity.
7. Retain the R7 full-code audit and Issue-040 inside the package for ZIP-only continuation.

## Test policy for this candidate

The implementation includes regression code, but no unit/deterministic/live test is executed in this
wave because the user explicitly deferred tests until MinIO is prepared. Therefore Issue-040 is not
marked CLOSED and this package must not be described as deterministic accepted.

Allowed package checks are static source inspection, JSON/AST parsing, manifest regeneration, ZIP
integrity and source-diff verification; they are not substitutes for deferred acceptance tests.

## Stop condition

When tests resume, Issue-040 can close only after:

- the normal current document validator passes;
- the deliberate stale nested Runtime PLANS regression proves the validator fails closed;
- Workspace unit/deterministic regression passes from a clean extraction;
- historical evidence remains byte/identity-retained where intended.
