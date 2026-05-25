@echo off
set "APPDIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%APPDIR%scripts\repair_server_env.ps1" -AppPath "%APPDIR%"
pause
