@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Run sh_setup.cmd first.
  exit /b 1
)
".venv\Scripts\python.exe" scripts\run_step048_acceptance.py
exit /b %ERRORLEVEL%
