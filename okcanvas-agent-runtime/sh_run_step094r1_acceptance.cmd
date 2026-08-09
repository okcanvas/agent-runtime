@echo off
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo Runtime virtual environment is missing. Run sh_setup_workspace.cmd from the workspace root first. 1>&2
  exit /b 2
)
"%ROOT%.venv\Scripts\python.exe" "%ROOT%scripts\run_step094r1_acceptance.py" %*
exit /b %ERRORLEVEL%
