@echo off
setlocal
cd /d %~dp0
.venv\Scripts\python.exe scripts\python_bytecode_isolation.py scripts\run_step091b3_acceptance.py %*
exit /b %ERRORLEVEL%
