# WORKSPACE-ISSUE-015 — Windows Workspace orchestrator reused bootstrap Python

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Actual failure

The real Windows STEP003R1 run resolved the Workspace bootstrap interpreter as:

```text
C:\Python312\python.exe
```

The same interpreter was then reused for three boundaries that are explicitly owned by independent project environments:

```text
Connector retained acceptance       -> No module named pytest
Connector -> Example E2E            -> No module named fastapi
Main Assistant full E2E             -> No module named uvicorn
```

The project catalog already declared separate `.venv` environments for Runtime and Connector. The runner violated that declaration by using `sys.executable` for every Python subprocess.

## Root cause

The Workspace launcher and runner treated the Python used to start the orchestration script as a shared dependency environment. The Workspace root intentionally has no `.venv`, so this conflated the bootstrap interpreter with product-owned interpreters.

## Correction

STEP003R2 adds `resolve_project_python` and enforces the following execution ownership:

```text
Workspace unittest orchestration        bootstrap Python
Connector retained acceptance           Connector .venv Python
Connector -> Example E2E                Connector .venv Python
Main Assistant / Runtime full E2E        Runtime .venv Python
```

On Windows, an existing project `.venv` must be selected exactly. In deterministic packaging environments where `.venv` directories are intentionally absent, a fallback is allowed only after importing the required modules successfully.

If no dependency-capable interpreter exists, the runner fails closed with an instruction to run `sh_setup_workspace.cmd`.

## Recurrence gates

- Static test verifies Connector acceptance no longer uses `sys.executable`.
- Static test verifies Connector E2E uses `connector_python`.
- Static test verifies Main Assistant E2E uses `runtime_python`.
- Integrated evidence records bootstrap, Runtime and Connector interpreter paths independently.
- If a project `.venv` exists, the selected interpreter must equal that `.venv` interpreter.
- Windows paths are passed as argv, not split command strings.
