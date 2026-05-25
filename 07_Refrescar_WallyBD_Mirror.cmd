@echo off
cd /d "%~dp0"
call .venv\Scripts\python.exe scripts\refresh_wallybd_mirror.py --app-path "%~dp0"
pause
