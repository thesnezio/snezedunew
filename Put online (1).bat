@echo off
cd /d "%~dp0"
echo Quick update: only the app files changed since the last quick update go online (no lessons, no database).
echo To send every app file again: python upload_ui_only.py --all
echo New Python packages (pypdf, openpyxl, pillow) need "Put online.bat" once.
python upload_ui_only.py %*
pause
