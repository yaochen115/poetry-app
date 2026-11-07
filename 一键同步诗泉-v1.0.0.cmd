@echo off
powershell.exe -NoProfile -File "%~dp0scripts\sync_poetry_api_v1_0_0.ps1" %*
set "sync_exit=%errorlevel%"
pause
exit /b %sync_exit%
