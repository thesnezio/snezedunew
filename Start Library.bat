@echo off
title Lesson Library
rem Double-click to start the Lesson Library app. It opens in your browser; keep this window open while you use it.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\run.ps1" app\server.py
echo.
pause
