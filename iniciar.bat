@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Execute instalar.bat primeiro.
  pause
  exit /b 1
)
if not defined STUDIO_PORT set STUDIO_PORT=5050
echo Abra http://127.0.0.1:%STUDIO_PORT% no navegador quando o servidor iniciar.
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
