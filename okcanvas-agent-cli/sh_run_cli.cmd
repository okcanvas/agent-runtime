@echo off
setlocal
cd /d "%~dp0"
if not exist "package.json" (
  echo [ERROR] Product CLI project root is invalid.
  exit /b 3
)
node src\cli.mjs %*
exit /b %ERRORLEVEL%
