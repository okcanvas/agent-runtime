# OR-ISSUE-057 — STEP082B current next-step and preserved Skill assertions remained stale

## Symptom

The STEP082B full Python regression failed 14 tests in files 180–199. Thirteen assertions expected `UNSELECTED_PENDING_STEP081D_WINDOWS_LIVE_ACCEPTANCE` although STEP081D was already live accepted and RuntimeInfo selected STEP083. One assertion required the preserved `document-review-v1` Skill to remain visible in HANDOFF, but the rewritten HANDOFF omitted it.

## Code-confirmed root cause

The earlier broad STEP/version alignment changed current Product identity but did not update every current-state `next_selected_step` assertion. The HANDOFF rewrite summarized STEP082B boundaries without restating the preserved Skill inventory required by an existing contract test.

## Impact

No Product execution behavior failed. The stale tests contradicted the promoted Product state, and the HANDOFF was incomplete for ZIP-only continuation.

## Correction

Current-state tests now expect `STEP083_ORGANIZATION_ASSISTANT_MAIN_AGENT_AND_ACTION_ROUTING_FOUNDATION`. Historical STEP081D runner source and immutable evidence remain unchanged. HANDOFF now explicitly preserves `document-review-v1` and the existing capability inventory.

## Evidence

The original failed checkpoint and log are retained under `docs/evidence/step082b-local/python-regression/` during development. The corrected chunk and full regression must pass before packaging.

## Recurrence gate

- full STEP082B Python regression;
- `tests/test_step082b_coding_execution_plane_and_distribution_boundary.py` verifies the exact next selected STEP;
- preserved capability tests continue to require `document-review-v1` in HANDOFF.
