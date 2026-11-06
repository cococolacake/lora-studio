@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo LoRA Studio isn't set up yet. Run Install.bat first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" main.py %*
