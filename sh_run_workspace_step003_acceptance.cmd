@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-runtime\pyproject.toml" goto :invalid
if not exist "okcanvas-agent-cli\package.json" goto :invalid
if not exist "okcanvas-connectors\groupware-mcp-server\pyproject.toml" goto :invalid
if not exist "okcanvas-connector-examples\groupware\groupware-api-fake\package.json" goto :invalid
if exist "pyproject.toml" goto :invalid
call sh_run_workspace_step003r2_acceptance.cmd %*
exit /b %ERRORLEVEL%
:invalid
echo Workspace root is invalid: %CD% 1>&2
exit /b 2
