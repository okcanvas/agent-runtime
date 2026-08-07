@echo off
setlocal
cd /d "%~dp0"
if not exist "okcanvas-agent-cli\package.json" (
  echo [ERROR] Workspace root is invalid: okcanvas-agent-cli\package.json is missing. 1>&2
  exit /b 2
)
call sh_run_workspace_step007r1_live_acceptance.cmd %*
exit /b %ERRORLEVEL%
