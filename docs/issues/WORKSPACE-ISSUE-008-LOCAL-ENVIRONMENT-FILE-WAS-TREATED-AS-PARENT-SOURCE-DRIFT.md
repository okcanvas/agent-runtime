# WORKSPACE-ISSUE-008 — Local environment file was treated as parent source drift

## Observed Windows failure

The real Windows `WORKSPACE_STEP001R2` run reached all child acceptances, but workspace identity failed
because `okcanvas-agent-runtime/.env.local` was included in the current-file comparison and workspace
manifest while the immutable parent manifest correctly did not contain local secrets/configuration.

## Root cause

Workspace inventory logic duplicated exclusion rules and omitted `.env`, `.env.local`, and
`.env.local.cmd`, despite the Runtime product constitution already defining them as local mutable data.

## Correction

- one shared `scripts/workspace_inventory.py` owns workspace and parent-project exclusions;
- exact local environment filenames are excluded from identity, manifest, and packaging;
- `.env.local.example` remains included and immutable;
- pre/post child-project snapshots prove acceptance does not mutate source.

## Recurrence gate

`test_local_environment_files_are_excluded_from_identity_and_package` and the Windows acceptance check
`local_environment_excluded_from_identity` must pass.
