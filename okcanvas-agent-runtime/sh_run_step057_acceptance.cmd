@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv is missing. Run sh_setup.cmd first.
  exit /b 2
)
".venv\Scripts\python.exe" scripts\run_step057_acceptance.py %*
exit /b %ERRORLEVEL%
