@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\pythonw.exe" (
  echo Project virtual environment not found. Please install requirements.txt first.
  pause
  exit /b 1
)
start "" "venv\Scripts\pythonw.exe" "desktop_entry.py"
