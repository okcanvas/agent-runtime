@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Project virtual environment not found. Run sh_setup.cmd first.
  exit /b 2
)
".venv\Scripts\python.exe" scripts\run_step050_acceptance.py %*
exit /b %ERRORLEVEL%
