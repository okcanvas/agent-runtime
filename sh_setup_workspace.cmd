@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-runtime\pyproject.toml" goto invalid_root
if not exist "okcanvas-agent-cli\package.json" goto invalid_root
if not exist "okcanvas-connectors\groupware-mcp-server\pyproject.toml" goto invalid_root
if not exist "okcanvas-connectors\organization-context-mcp-server\pyproject.toml" goto invalid_root
if not exist "okcanvas-connector-examples\groupware\groupware-api-fake\package.json" goto invalid_root
if not exist "okcanvas-connector-examples\organization-context\organization-context-api-fake\package.json" goto invalid_root

echo [1/6] Agent Runtime environment
call okcanvas-agent-runtime\sh_setup.cmd
if errorlevel 1 exit /b %ERRORLEVEL%

echo [2/6] Groupware Connector environment
if not exist "okcanvas-connectors\groupware-mcp-server\.venv\Scripts\python.exe" (
  py -3 -m venv "okcanvas-connectors\groupware-mcp-server\.venv"
  if errorlevel 1 exit /b %ERRORLEVEL%
)
"okcanvas-connectors\groupware-mcp-server\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b %ERRORLEVEL%
"okcanvas-connectors\groupware-mcp-server\.venv\Scripts\python.exe" -m pip install -e "okcanvas-connectors\groupware-mcp-server" pytest
if errorlevel 1 exit /b %ERRORLEVEL%

echo [3/6] Organization Context Connector environment
if not exist "okcanvas-connectors\organization-context-mcp-server\.venv\Scripts\python.exe" (
  py -3 -m venv "okcanvas-connectors\organization-context-mcp-server\.venv"
  if errorlevel 1 exit /b %ERRORLEVEL%
)
"okcanvas-connectors\organization-context-mcp-server\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b %ERRORLEVEL%
"okcanvas-connectors\organization-context-mcp-server\.venv\Scripts\python.exe" -m pip install -e "okcanvas-connectors\organization-context-mcp-server" pytest
if errorlevel 1 exit /b %ERRORLEVEL%

echo [4/6] Product Service CLI environment
pushd okcanvas-agent-cli
call npm ci --ignore-scripts
if errorlevel 1 (popd & exit /b %ERRORLEVEL%)
popd

echo [5/6] Groupware API Example environment
pushd okcanvas-connector-examples\groupware\groupware-api-fake
call npm ci --ignore-scripts --offline
if errorlevel 1 (popd & exit /b %ERRORLEVEL%)
popd

echo [6/6] Organization Context API Example environment
pushd okcanvas-connector-examples\organization-context\organization-context-api-fake
call npm ci --ignore-scripts --offline
if errorlevel 1 (popd & exit /b %ERRORLEVEL%)
popd

echo [OK] Independent project environments are ready.
exit /b 0

:invalid_root
echo [ERROR] Workspace root is invalid.
echo [ERROR] Extract the ZIP as D:\NODE_AGENTS\okcanvas-agent-platform and run this command there.
exit /b 3
