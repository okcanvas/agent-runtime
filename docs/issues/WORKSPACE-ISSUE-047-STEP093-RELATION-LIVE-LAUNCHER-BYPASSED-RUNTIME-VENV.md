# WORKSPACE-ISSUE-047 — STEP093 relation Live launcher bypassed Runtime venv

## Status

FIX_IMPLEMENTED_RELATION_LIVE_RERUN_REQUIRED

## Observed failure

After `sh_setup_workspace.cmd`, the first actual Windows run of:

```bat
sh_run_workspace_step008r4r9_relation_live_acceptance
```

failed before the focused STEP093 harness loaded:

```text
ModuleNotFoundError: No module named 'uvicorn'
```

## Code-proven root cause

`sh_setup_workspace.cmd` delegates Runtime setup to `okcanvas-agent-runtime\sh_setup.cmd`. That script creates `okcanvas-agent-runtime\.venv` and runs `pip install -e .`. Runtime `pyproject.toml` declares `uvicorn>=0.35,<1`, so `uvicorn` belongs to that Runtime environment.

The accepted base launcher `sh_run_workspace_step008_live_acceptance.cmd` correctly invokes:

```text
okcanvas-agent-runtime\.venv\Scripts\python.exe
  scripts\workspace_python_bytecode_isolation.py
  scripts\run_workspace_step008_live_entrypoint.py
```

The new STEP093 focused relation launcher incorrectly used:

```text
.workspace-venv\Scripts\python.exe if present
otherwise py -3
```

`sh_setup_workspace.cmd` never creates `.workspace-venv`. On the user's machine the fallback therefore selected the system Python, which did not contain Runtime dependencies such as `uvicorn`.

## Correction

The relation launcher now mirrors the proven base Live launcher contract:

1. validate Workspace root;
2. require `okcanvas-agent-runtime\.venv\Scripts\python.exe`;
3. instruct the operator to run `sh_setup_workspace.cmd` when the Runtime environment is absent;
4. execute the relation entrypoint through Runtime `.venv`;
5. wrap execution in `workspace_python_bytecode_isolation.py` so Live execution cannot dirty the canonical package with bytecode caches.

No Runtime Product source or STEP093 relation semantics were changed.

## Recurrence prevention

A source regression now compares the focused relation launcher with the base Live launcher's environment contract and rejects `py -3` / `.workspace-venv` fallback paths.
