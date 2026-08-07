@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher ^(py^) was not found.
  exit /b 2
)

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 exit /b %ERRORLEVEL%
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b %ERRORLEVEL%

".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 exit /b %ERRORLEVEL%

echo [OK] Python environment is ready.
echo [NOTE] Codex CLI must also be installed and available on PATH or CODEX_PATH.
exit /b 0
