@echo off
title SnezEdu helper
cd /d "%~dp0"
echo SnezEdu online uses Claude Code on this computer (your Claude subscription).
echo Leave this window open. Close it to stop.
echo.
python app\helper.py %*
pause
