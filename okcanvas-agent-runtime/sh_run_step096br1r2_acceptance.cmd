@echo off
setlocal
set "ROOT=%~dp0"
if exist "%ROOT%.venv\Scripts\python.exe" (
  "%ROOT%.venv\Scripts\python.exe" "%ROOT%scripts\run_step096br1r2_acceptance.py" %*
) else (
  python "%ROOT%scripts\run_step096br1r2_acceptance.py" %*
)
exit /b %ERRORLEVEL%
