@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv\Scripts\python.exe 1>&2
  exit /b 1
)
".venv\Scripts\python.exe" scripts\python_bytecode_isolation.py scripts\run_step086r1_acceptance.py %*
exit /b %ERRORLEVEL%
