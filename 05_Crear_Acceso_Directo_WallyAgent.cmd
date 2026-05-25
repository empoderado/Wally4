@echo off
set "APPDIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%APPDIR%scripts\create_shortcut.ps1" -AppPath "%APPDIR:~0,-1%"
pause
