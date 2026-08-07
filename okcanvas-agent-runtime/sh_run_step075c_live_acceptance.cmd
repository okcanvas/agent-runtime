@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Missing .venv. Run sh_setup.cmd first.
  exit /b 1
)
".venv\Scripts\python.exe" scripts\python_bytecode_isolation.py scripts\windows_entrypoint.py readonly-sandbox-workspace-tar-stream-live-acceptance %*
exit /b %ERRORLEVEL%
