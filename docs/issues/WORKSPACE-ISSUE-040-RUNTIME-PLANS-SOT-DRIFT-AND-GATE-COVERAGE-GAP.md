# WORKSPACE-ISSUE-040 — Runtime PLANS SOT drift and current-document gate coverage gap

```text
ID: WORKSPACE-ISSUE-040
Discovered by: WORKSPACE_STEP008R4R7_FULL_CODE_GAP_READ_ONLY_AUDIT
Status: FIX_IMPLEMENTED_TEST_EXECUTION_DEFERRED_BY_USER
Source Workspace: STEP008R4R7 / 0.8.4-r7
Source Runtime: STEP091D / 2.75.0
Product source modifications: 0
Test execution: DEFERRED_BY_USER_UNTIL_MINIO_READY
```

## Failure

The current release ZIP contains contradictory current-state planning documents:

- root `PLANS.md` identifies STEP008R4R7 / STEP091D / 2.75.0 and parent real PostgreSQL 19/19 accepted;
- `okcanvas-agent-runtime/PLANS.md` still identifies STEP091B3R1 / 2.74.1 and lists real PostgreSQL acceptance as pending;
- the Productization Master Plan immediate backlog still uses STEP091C-era ordering.

The current document regression did not catch this because
`tests/test_workspace_step008r4r1_document_plan_and_storage_audit.py`:

1. omits `okcanvas-agent-runtime/PLANS.md` from the current document list;
2. concatenates the listed documents before checking for the current Step token, allowing a
   correct document to mask a stale sibling document.

## Why this matters

The workspace policy requires another conversation to continue correctly from the ZIP alone.
A stale Runtime plan can reopen already accepted work or cause the next wave to be selected
from an obsolete baseline.

This is the same failure family as earlier stale current-document/current-identity issues,
but the missing per-file SOT gate is the specific recurrence mechanism observed here.

## Required correction

A follow-up corrective Step should:

1. align root and Runtime current `PLANS.md`, HANDOFF and Productization Master Plan;
2. update issue registries with current STEP091D findings;
3. define one machine-readable current Workspace/Runtime baseline SOT;
4. validate **each** current-state document independently against that SOT;
5. retain historical documents/evidence without rewriting their historical identity;
6. retain a regression that deliberately makes one nested current plan stale and proves the
   gate fails.

## Stop condition

Do not solve this by replacing every historical Step token with the newest token. Historical
evidence must remain immutable.

Do not claim this Issue fixed until the correction has deterministic regression evidence.
This audit itself is READ_ONLY and does not modify the release ZIP.

## STEP008R4R7A correction status

The corrective Workspace wave `WORKSPACE_STEP008R4R7A_CURRENT_DOCUMENT_SOT_ALIGNMENT_AND_PER_FILE_IDENTITY_GATE` implements the required structure:

- `specs/workspace/current-baseline.json` is the machine-readable current Workspace/Runtime identity SOT;
- root and Runtime current README/HANDOFF/PLANS plus the Productization Master Plan carry one exact marker block;
- `scripts/validate_current_document_sot.py` validates each current document independently;
- current Workspace manifest/acceptance scripts derive identity from the SOT;
- a regression test deliberately stales nested Runtime `PLANS.md` and requires fail-closed behavior.

A static SOT validation was performed during packaging, but unit/deterministic/live test execution is intentionally deferred by user direction until MinIO is prepared. Therefore this issue is **not CLOSED** yet. The close condition remains deterministic regression evidence, including the deliberate stale nested-plan negative case.
