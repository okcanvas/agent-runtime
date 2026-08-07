@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv is missing. Run sh_setup.cmd first.
  exit /b 2
)

".venv\Scripts\python.exe" scripts\python_bytecode_isolation.py scripts\windows_entrypoint.py control-api %*
exit /b %ERRORLEVEL%
