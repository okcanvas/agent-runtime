# OR-ISSUE-028 — Declarative Client path and Client layout documentation remained stale

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

The Service Client policy still declared `clients/okcanvas-agent-cli`, while the actual STEP081 workspace is `clients/cli`. Historical tests also attempted to open absent repository-root directories `agent-cli/`, `agent-web/`, and `agent-desktop/`. The current Client README continued to describe those absent roots as the planned physical layout.

## Code-confirmed root cause

Python and Node source movement was updated, but non-Python policy and documentation references were outside the executable legacy-path scan. The service policy hash assertion then also remained bound to the pre-STEP081 identity.

## Impact

Service capability metadata could advertise a nonexistent development harness path, ZIP-only handoff documentation described the wrong tree, and complete regression failed despite the actual Client workspaces being present.

## Fix

- changed the Service Client policy harness path to `clients/cli`;
- documented `clients/cli`, `clients/web`, `clients/desktop`, and `clients/dev-cli` as the actual STEP081 Client workspaces;
- aligned the exact policy SHA and Client-root regression with the current Product tree.

## Recurrence-prevention gate

`declarative_path_references_current` requires every repository-relative path declared by the Service Client policy to exist. STEP069 regressions verify the exact policy SHA and all three current Client workspace READMEs.
