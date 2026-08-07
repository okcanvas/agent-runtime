@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Project virtual environment is missing. Run sh_setup.cmd first.
  exit /b 1
)
".venv\Scripts\python.exe" scripts\run_step059a_acceptance.py %*
exit /b %ERRORLEVEL%
