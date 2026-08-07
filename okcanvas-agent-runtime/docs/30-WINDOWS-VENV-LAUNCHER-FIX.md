# Windows project-venv launcher fix

STEP030A repairs the Windows launcher that blocked STEP030 before Product acceptance began.

## Confirmed failure path

```text
sh_run_step030_acceptance.cmd
→ PATH python
→ scripts/windows_entrypoint.py
→ same PATH interpreter via sys.executable
→ import fastapi.testclient
→ ModuleNotFoundError
```

`sh_setup.cmd` had installed FastAPI into the project `.venv`; the launcher bypassed that environment.

## Corrected path

```text
sh_run_step030_acceptance.cmd
→ verify .venv\Scripts\python.exe exists
→ project .venv Python
→ scripts/windows_entrypoint.py
→ same project interpreter via sys.executable
→ scripts/run_step030_acceptance.py
```

The launcher does not activate a shell environment and does not execute `.env.local`. It directly selects the canonical project interpreter.

## Regression prevention

Every `sh_*.cmd` runtime launcher except `sh_setup.cmd` is scanned by tests. A bare `python` or launcher without `.venv\Scripts\python.exe` fails the suite.

STEP030A changes no Product authority or business behavior.
