@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe scripts\run_step096a_acceptance.py %*
) else (
  python scripts\run_step096a_acceptance.py %*
)
exit /b %errorlevel%
