@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-runtime\.venv\Scripts\python.exe" (
  echo [ERROR] Runtime Python environment is missing. Run sh_setup_workspace.cmd first. 1>&2
  exit /b 2
)
"okcanvas-agent-runtime\.venv\Scripts\python.exe" scripts\workspace_python_bytecode_isolation.py scripts\run_workspace_step008r4r10_cross_domain_live_entrypoint.py %*
exit /b %ERRORLEVEL%
