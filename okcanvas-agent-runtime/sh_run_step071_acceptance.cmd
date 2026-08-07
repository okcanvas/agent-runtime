@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo STEP071_FAIL virtual_environment_not_found
  exit /b 1
)
".venv\Scripts\python.exe" scripts\run_step071_acceptance.py %*
exit /b %ERRORLEVEL%
