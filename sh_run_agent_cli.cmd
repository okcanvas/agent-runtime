@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-cli\src\cli.mjs" (
  echo [ERROR] Workspace root is invalid.
  echo [ERROR] Run from D:\NODE_AGENTS\okcanvas-agent-platform.
  exit /b 3
)
call okcanvas-agent-cli\sh_run_cli.cmd %*
exit /b %ERRORLEVEL%
