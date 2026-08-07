# WORKSPACE-ISSUE-006 — Mutable acceptance evidence broke deterministic repack

## Symptom

The source and Fresh Workspace acceptances both passed, but a Fresh repack produced a different ZIP SHA-256.

## Confirmed cause

`run_workspace_step001r1_acceptance.py` rewrites
`docs/evidence/WORKSPACE_STEP001R1_ACCEPTANCE.json` with current timestamps and process output.
`WORKSPACE_MANIFEST.json` already excluded this mutable evidence, but `package_workspace.py` did not.
The same source tree therefore packaged different bytes after acceptance.

## Correction

- Exclude both Workspace acceptance JSON files from the source ZIP.
- Keep immutable parent Windows evidence in the ZIP.
- Add a source regression that asserts the mutable evidence exclusion boundary.
- Require byte-identical deterministic repack in Final Fresh validation.

## Recurrence gate

`tests/test_workspace_windows_execution.py::test_mutable_acceptance_evidence_is_excluded_from_workspace_package`
