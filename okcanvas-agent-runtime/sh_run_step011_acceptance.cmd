@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe scripts\windows_entrypoint.py catalog-acceptance %*
exit /b %ERRORLEVEL%
