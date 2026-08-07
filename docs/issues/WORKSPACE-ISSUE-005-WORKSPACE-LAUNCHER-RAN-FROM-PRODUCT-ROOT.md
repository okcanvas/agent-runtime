# WORKSPACE-ISSUE-005 — Workspace launcher ran from a product root

## Failure

The user executed `sh_run_workspace_step001_acceptance` from
`D:\NODE_AGENTS\okcanvas-agent-runtime`. A Workspace launcher and script had been copied or overlaid into
the old Runtime root, so execution continued without proving that the new sibling Workspace layout existed.

## Correction

All Workspace launchers and the Python acceptance now fail closed unless the management root is named
`okcanvas-agent-platform` and contains the Runtime, Product CLI, Connector, and Example sibling project
markers. The error message provides the exact extraction and execution location.

## Recurrence gates

- Reject a root containing a product-level `pyproject.toml`.
- Require all four sibling project markers before setup or acceptance.
- Unit-test rejection of an `okcanvas-agent-runtime` product root.
- Keep compatibility launcher names, but route them to the current corrective acceptance only after root validation.
