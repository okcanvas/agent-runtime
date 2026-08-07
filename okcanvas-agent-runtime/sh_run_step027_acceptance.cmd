@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\python.exe scripts\windows_entrypoint.py commerce-ingress-failure-matrix-acceptance %*
exit /b %ERRORLEVEL%
