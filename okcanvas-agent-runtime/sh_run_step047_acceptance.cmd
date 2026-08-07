@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Missing .venv. Run sh_setup.cmd first.
  exit /b 1
)
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" scripts\run_step047_acceptance.py
exit /b %ERRORLEVEL%
