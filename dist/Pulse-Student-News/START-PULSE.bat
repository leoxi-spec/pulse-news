@echo off
REM Pulse — Student News. Double-click this file on Windows.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Pulse needs Python 3. Install it from https://www.python.org/downloads/ and try again.
  pause
  exit /b 1
)
start "Pulse server" /b python run.py
timeout /t 3 /nobreak >nul
start "" "http://localhost:8787"
