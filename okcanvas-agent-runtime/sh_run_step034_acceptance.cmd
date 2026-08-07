@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv is missing. Run sh_setup.cmd first.
  exit /b 2
)
".venv\Scripts\python.exe" scripts\windows_entrypoint.py orphaned-running-reconciliation-acceptance %*
exit /b %ERRORLEVEL%
