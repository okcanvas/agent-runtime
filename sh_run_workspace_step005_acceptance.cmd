@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-runtime\pyproject.toml" goto invalid_root
if not exist "okcanvas-agent-cli\package.json" goto invalid_root
if not exist "okcanvas-connectors\groupware-mcp-server\pyproject.toml" goto invalid_root
if not exist "okcanvas-connectors\organization-context-mcp-server\pyproject.toml" goto invalid_root
if not exist "okcanvas-connector-examples\groupware\groupware-api-fake\package.json" goto invalid_root
if not exist "okcanvas-connector-examples\organization-context\organization-context-api-fake\package.json" goto invalid_root
call sh_run_workspace_step005r1_acceptance.cmd %*
exit /b %ERRORLEVEL%
:invalid_root
echo [ERROR] Workspace root is invalid.
exit /b 3
