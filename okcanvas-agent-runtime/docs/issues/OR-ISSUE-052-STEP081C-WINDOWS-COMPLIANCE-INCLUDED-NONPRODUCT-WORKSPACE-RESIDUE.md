# OR-ISSUE-052 — STEP081C Windows Compliance included non-Product workspace residue

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_VALIDATION_PENDING_WINDOWS_RERUN`

## Observed failure

The real Windows STEP081C Compliance result compared 1,278 actual changed files against 1,264 declared changed files. The 14 unregistered paths were:

- 12 files under `docs/evidence/step081b-python-regression/`
- `okcanvas-agent-runtime-step076-product-owned-immutable-project-snapshot-binding.zip`
- `yarn.lock`

These paths were not members of the final STEP081C Product ZIP. The Windows working directory therefore contained non-Product residue in addition to the extracted distribution.

The evidence proves workspace content drift. It does not prove the exact operation that introduced each file.

## Impact

The exact-diff Compliance Gate failed even though the extra files were known local archives, a local lockfile, and superseded local regression output. The output did not distinguish Product mutation from classified workspace residue.

## Corrective implementation

STEP081D keeps unknown executable or Product-path additions fail-closed, while explicitly classifying and excluding only these known non-Product categories:

- root-local ZIP/SHA archives,
- root-local `yarn.lock`,
- superseded `docs/evidence/step081b-python-regression/` output.

The classified residue list is preserved in Compliance output. It is not admitted into the Product file map or final ZIP.

## Recurrence gates

- `tests/test_step081d_windows_source_identity_router_registration_and_workspace_residue.py`
- `workspace_residue_classified`
- exact Product changed-file comparison
- final ZIP forbidden/local-residue inspection
