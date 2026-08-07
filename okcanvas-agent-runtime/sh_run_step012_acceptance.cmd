@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe scripts\windows_entrypoint.py recorded-evaluation-acceptance %*
exit /b %ERRORLEVEL%
