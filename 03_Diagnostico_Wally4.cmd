@echo off
set "APPDIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%APPDIR%scripts\diagnostics.ps1" -AppPath "%APPDIR%"
pause
