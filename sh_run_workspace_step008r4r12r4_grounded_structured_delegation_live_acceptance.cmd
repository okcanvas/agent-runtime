@echo off
setlocal
cd /d "%~dp0"
if exist "okcanvas-agent-runtime\.venv\Scripts\python.exe" (
  "okcanvas-agent-runtime\.venv\Scripts\python.exe" scripts\run_workspace_step008r4r12r4_grounded_structured_delegation_live_entrypoint.py %*
) else (
  python scripts\run_workspace_step008r4r12r4_grounded_structured_delegation_live_entrypoint.py %*
)
exit /b %ERRORLEVEL%
