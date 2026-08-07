@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js 22 or newer is required on PATH.
  exit /b 2
)
node "clients\cli\dist\cli.js" %*
exit /b %ERRORLEVEL%
