@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-runtime\pyproject.toml" goto invalid_root
if not exist "okcanvas-agent-cli\package.json" goto invalid_root
if not exist "okcanvas-connectors\groupware-mcp-server\pyproject.toml" goto invalid_root
if not exist "okcanvas-connector-examples\groupware\groupware-api-fake\package.json" goto invalid_root
call sh_run_workspace_step001r3_acceptance.cmd
exit /b %ERRORLEVEL%

:invalid_root
echo [ERROR] Workspace root is invalid.
echo [ERROR] Extract the ZIP as D:\NODE_AGENTS\okcanvas-agent-platform and run this command there.
exit /b 3
