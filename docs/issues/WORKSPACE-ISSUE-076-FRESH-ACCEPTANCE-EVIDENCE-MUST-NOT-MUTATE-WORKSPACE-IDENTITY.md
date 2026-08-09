# WORKSPACE-ISSUE-076 — Fresh acceptance evidence must not mutate Workspace identity

Status: FIXED_IN_R12R3_RELEASE_VALIDATION

## Symptom

Running `okcanvas-agent-runtime/scripts/run_step096br1r1_acceptance.py` with its default output inside a Fresh extracted package rewrote `okcanvas-agent-runtime/docs/evidence/STEP096BR1R1_DETERMINISTIC_ACCEPTANCE.json`. The payload includes the pytest timing summary, so the file bytes can differ between runs. Because that deterministic evidence path is part of `WORKSPACE_MANIFEST.json`, the subsequent Workspace static gate dropped from 22/22 to 21/22 even though Product behavior was unchanged.

## Root cause

Fresh release validation used the acceptance runner's in-tree default output instead of its supported explicit output-path argument. A runtime/timing-bearing validation result was therefore allowed to mutate the immutable package identity being validated.

## Closure

- Fresh release validation MUST invoke `run_step096br1r1_acceptance.py <external-output-path>` outside the extracted Workspace tree.
- Release validation MUST rerun the Workspace static manifest gate after all deterministic/runtime gates.
- The package contents and Product contracts are not relaxed or excluded to accommodate validation-time mutation.
- Historical deterministic evidence already packaged remains immutable evidence for the source acceptance run; fresh validation output is ephemeral and external.

## Recurrence rule

Never run a validator/acceptance runner with a default in-tree evidence output against a tree whose byte identity is being verified. If an external output parameter exists, use it. If it does not exist, add a non-mutating validation path before claiming Fresh deterministic reproducibility.
