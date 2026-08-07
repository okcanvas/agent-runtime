@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-cli\package.json" (
  echo [ERROR] Workspace root is invalid: okcanvas-agent-cli\package.json is missing. 1>&2
  exit /b 2
)
if not exist "okcanvas-agent-runtime\.venv\Scripts\python.exe" (
  echo [ERROR] Runtime Python environment is missing. Run sh_setup_workspace.cmd first. 1>&2
  exit /b 2
)
"okcanvas-agent-runtime\.venv\Scripts\python.exe" scripts\workspace_python_bytecode_isolation.py scripts\run_workspace_step008_acceptance.py %*
exit /b %ERRORLEVEL%
