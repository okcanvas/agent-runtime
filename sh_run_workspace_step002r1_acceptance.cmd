@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-runtime\pyproject.toml" goto invalid_root
if not exist "okcanvas-agent-cli\package.json" goto invalid_root
"okcanvas-agent-runtime\.venv\Scripts\python.exe" scripts\run_workspace_step002r1_acceptance.py
exit /b %ERRORLEVEL%
:invalid_root
echo [ERROR] Workspace root is invalid.
echo [ERROR] Extract the ZIP as D:\NODE_AGENTS\okcanvas-agent-platform and run this command there.
exit /b 3
