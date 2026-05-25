@echo off
set "APPDIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '%APPDIR%.venv\Scripts\python.exe' '%APPDIR%scripts\validate_real_data_mode.py'"
pause
