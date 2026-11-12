@echo off
cd /d "%~dp0"
echo ============================================================
echo  SnezEdu - quick update online (PythonAnywhere)
echo  Sends only the app files and skills changed since the last
echo  quick update, then reloads the site. Lessons and the online
echo  database are not touched.
echo ============================================================
if not exist "%~dp0_pa_login.json" (
  echo No saved login yet: run "Put online.bat" once first.
  pause
  exit /b 1
)
python upload_ui_only.py %*
echo.
echo Then open the site and press Ctrl+F5.
pause
