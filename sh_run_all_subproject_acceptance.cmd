@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-runtime\pyproject.toml" goto invalid_root
if not exist "okcanvas-agent-cli\package.json" goto invalid_root
if not exist "okcanvas-connectors\groupware-mcp-server\pyproject.toml" goto invalid_root
if not exist "okcanvas-connectors\organization-context-mcp-server\pyproject.toml" goto invalid_root
if not exist "okcanvas-connector-examples\groupware\groupware-api-fake\package.json" goto invalid_root
if not exist "okcanvas-connector-examples\organization-context\organization-context-api-fake\package.json" goto invalid_root

echo [1/6] Runtime STEP087R2 retained
call okcanvas-agent-runtime\sh_run_step087r2_acceptance.cmd
if errorlevel 1 exit /b %ERRORLEVEL%

echo [2/6] Product Service CLI STEP001R1
pushd okcanvas-agent-cli
call npm run acceptance
if errorlevel 1 (popd & exit /b %ERRORLEVEL%)
popd

echo [3/6] Groupware Connector STEP001R1
"okcanvas-connectors\groupware-mcp-server\.venv\Scripts\python.exe" "okcanvas-connectors\groupware-mcp-server\scripts\run_acceptance.py"
if errorlevel 1 exit /b %ERRORLEVEL%

echo [4/6] Groupware API Example STEP001R1
pushd okcanvas-connector-examples\groupware\groupware-api-fake
call npm run acceptance
if errorlevel 1 (popd & exit /b %ERRORLEVEL%)
popd

echo [5/6] Organization Context Connector STEP001
"okcanvas-connectors\organization-context-mcp-server\.venv\Scripts\python.exe" "okcanvas-connectors\organization-context-mcp-server\scripts\run_acceptance.py"
if errorlevel 1 exit /b %ERRORLEVEL%

echo [6/6] Organization Context API Example STEP001
pushd okcanvas-connector-examples\organization-context\organization-context-api-fake
call npm run acceptance
if errorlevel 1 (popd & exit /b %ERRORLEVEL%)
popd

echo [OK] All subproject acceptances passed.
exit /b 0

:invalid_root
echo [ERROR] Workspace root is invalid.
echo [ERROR] Extract the ZIP as D:\NODE_AGENTS\okcanvas-agent-platform and run this command there.
exit /b 3
