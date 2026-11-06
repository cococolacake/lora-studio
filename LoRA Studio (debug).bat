@echo off
REM Same as LoRA Studio.bat but keeps a console open (shows errors) and enables right-click > Inspect.
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py --debug %*
pause
