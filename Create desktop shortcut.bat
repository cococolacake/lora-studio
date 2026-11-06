@echo off
REM Puts a "LoRA Studio" shortcut (with the app icon) on your desktop.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\LoRA Studio.lnk'); $s.TargetPath='%~dp0.venv\Scripts\pythonw.exe'; $s.Arguments='main.py'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0web\assets\icon.ico'; $s.Description='LoRA Studio'; $s.Save()"
echo Shortcut created on your desktop.
pause
