@echo off
set "APPDIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%APPDIR%scripts\apply_wallybd_sql.ps1" -AppPath "%APPDIR%"
pause
