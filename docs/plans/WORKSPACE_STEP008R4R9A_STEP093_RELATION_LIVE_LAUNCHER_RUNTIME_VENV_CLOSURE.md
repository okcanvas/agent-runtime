# WORKSPACE STEP008R4R9A — STEP093 relation Live launcher Runtime venv closure

Current Workspace: WORKSPACE_STEP008R4R9A_STEP093_RELATION_LIVE_LAUNCHER_RUNTIME_VENV_CLOSURE
Workspace Version: 0.8.4-r9a
Current Runtime: STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL
Runtime Version: 2.77.0

## Scope

This is a Workspace-only corrective closure for the focused STEP093 relation Live launcher. It does not change Runtime STEP093 Product semantics.

## Root cause

The relation Live launcher diverged from the accepted base Live launcher and selected system Python when a non-standard `.workspace-venv` was absent. Workspace setup provisions `okcanvas-agent-runtime\.venv`; therefore the focused launcher could import no Runtime dependency from a clean Windows setup.

## Correct contract

The focused relation launcher must use the same environment boundary as the base Workspace Live launcher: Runtime `.venv` plus the bytecode-isolation wrapper. It must fail with a clear setup message if that Runtime environment is absent and must never fall back to `py -3`.

## Promotion boundary

Static validation can establish only that the launcher contract is corrected. Actual focused STEP093 relation Live acceptance remains pending until the operator re-runs the Windows command successfully.
