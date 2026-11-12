@echo off
cd /d "%~dp0"
echo Put the Lesson Library online (PythonAnywhere). See DEPLOY.md.
echo Updates send only the files changed since the last upload.
if exist "%~dp0_pa_login.json" (
  python upload_pythonanywhere.py
) else (
  echo Type the username exactly as on PythonAnywhere, with the same capitals.
  set /p PAUSER=Your PythonAnywhere username:
  python upload_pythonanywhere.py %PAUSER%
)
pause
