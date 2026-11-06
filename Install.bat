@echo off
setlocal
cd /d "%~dp0"
echo.
echo  Setting up LoRA Studio...
echo.
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv || goto :fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
echo.
echo  All done! Double-click "LoRA Studio.bat" to start.
echo.
pause
exit /b 0
:fail
echo.
echo  Setup failed. Make sure Python 3.10+ is installed and on PATH (python.org, tick "Add python.exe to PATH").
pause
exit /b 1
