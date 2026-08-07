@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\python.exe scripts\windows_entrypoint.py commerce-snapshot-identity-acceptance %*
exit /b %ERRORLEVEL%
