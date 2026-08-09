# Workspace R12R1 Handoff

Current Workspace: WORKSPACE_STEP008R4R12R1_STEP096B_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE_HARNESS
Workspace Version: 0.8.4-r12r1
Current Runtime: STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION
Runtime Version: 2.80.0

State: LIVE_ACCEPTANCE_HARNESS_READY_TEST_PENDING
Promotion: CANDIDATE_FOCUSED_WINDOWS_LIVE_TEST_PENDING

## What changed from R12

Workspace-only validation/handoff changes:

- added STEP096BR1 focused Windows/OpenAI Live harness and Windows launcher;
- added identity provenance hashes for harness/entrypoint/launcher;
- isolated eight semantic scenarios into dedicated Sessions;
- separated turn-local hint API traffic from execution-specialist traffic in evidence;
- corrected stale STEP096A successor narrative in the current Runtime README (WORKSPACE-ISSUE-071);
- added BR1 failure/recurrence log.

Runtime Product remains STEP096B/2.80.0. Organization/Groupware Connector Product implementations and
Examples are unchanged.


## Local/Fresh validation before Windows Live

- Workspace R12R1 static contract: **33/33 PASSED**.
- Runtime STEP096B static: **20/20 PASSED**.
- Runtime STEP096B deterministic acceptance: **6/6 PASSED**, focused pytest **63/63 PASSED**.
- Acceptance launcher registry: **7/7 PASSED**.
- Architecture constitution: **16/16 PASSED**.
- Current architecture: **39/40**, with only the intentionally historical STEP081 `identity_exact` check false; current physical module inventory and RuntimeInfo feature groups are exact.
- Runtime Product Python: **379/379 byte-exact** against the retained R12 parent Product-Python manifest.
- BR1 evidence output is registered in `MUTABLE_ACCEPTANCE_EVIDENCE` before packaging (WORKSPACE-ISSUE-072).
- No-environment BR1 preflight: **6/11**, expected fail-closed because the package contains no local OpenAI environment. No Live PASS is claimed.
- Fresh extraction reproduced the same current gates before packaging.

## Run next

```text
sh_run_workspace_step008r4r12r1_grounded_structured_delegation_live_acceptance
```

Expected result is a generated evidence JSON under:

```text
docs/evidence/WORKSPACE_STEP008R4R12R1_GROUNDED_STRUCTURED_DELEGATION_LIVE_ACCEPTANCE.json
```

Do not pre-fill expected pass counts in promotion metadata. Use the generated evidence as the source of truth.
If FAILED, inspect `failure_stage`, redacted CLI diagnostic and Runtime event diagnostic before changing Product.

R10ER1/STEP094R2 remains the last Windows-focused Live-promoted baseline until this gate passes.
