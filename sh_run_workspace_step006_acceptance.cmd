@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-runtime\pyproject.toml" goto invalid_root
if not exist "okcanvas-agent-cli\package.json" goto invalid_root
if not exist "okcanvas-connectors\organization-context-mcp-server\pyproject.toml" goto invalid_root
if not exist "okcanvas-connector-examples\organization-context\organization-context-api-fake\package.json" goto invalid_root
if not exist "okcanvas-agent-runtime\.venv\Scripts\python.exe" goto missing_env
"okcanvas-agent-runtime\.venv\Scripts\python.exe" scripts\workspace_python_bytecode_isolation.py scripts\run_workspace_step006_acceptance.py %*
exit /b %ERRORLEVEL%
:missing_env
echo [ERROR] Workspace environment is not ready. Run sh_setup_workspace.cmd first.
exit /b 2
:invalid_root
echo [ERROR] Workspace root is invalid.
exit /b 3
