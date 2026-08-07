@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-runtime\pyproject.toml" goto :invalid
if not exist "okcanvas-agent-cli\package.json" goto :invalid
if not exist "okcanvas-connectors\groupware-mcp-server\pyproject.toml" goto :invalid
if not exist "okcanvas-connector-examples\groupware\groupware-api-fake\package.json" goto :invalid
if exist "pyproject.toml" goto :invalid

if exist "okcanvas-agent-runtime\.venv\Scripts\python.exe" goto :runtime_python
where py >nul 2>nul
if not errorlevel 1 goto :py_launcher
where python >nul 2>nul
if not errorlevel 1 goto :path_python
goto :missing_python

:runtime_python
"%CD%\okcanvas-agent-runtime\.venv\Scripts\python.exe" scripts\run_workspace_step003r2_acceptance.py %*
exit /b %ERRORLEVEL%

:py_launcher
py -3 scripts\run_workspace_step003r2_acceptance.py %*
exit /b %ERRORLEVEL%

:path_python
python scripts\run_workspace_step003r2_acceptance.py %*
exit /b %ERRORLEVEL%

:missing_python
echo Python was not found. Run sh_setup_workspace.cmd after installing Python. 1>&2
exit /b 2

:invalid
echo Workspace root is invalid: %CD% 1>&2
exit /b 2
