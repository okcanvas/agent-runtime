@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Project virtual environment not found. Run sh_setup.cmd first.
  exit /b 1
)
".venv\Scripts\python.exe" scripts\run_step064_acceptance.py %*
exit /b %ERRORLEVEL%
