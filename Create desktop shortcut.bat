@echo off
REM Puts a "LoRA Studio" shortcut (with the app icon) on your desktop and in the Start menu.
REM Both carry LoRA Studio's app ID, so a pinned taskbar button opens LoRA Studio itself.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m studio.winshortcut
) else (
  python -m studio.winshortcut
)
pause
