@echo off
rem Double-click to rebuild lessons.json, search.json and index.html.
rem build_index.ps1 runs build_index.py with Python, fetching a portable Python first if none is installed.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_index.ps1"
echo.
pause
