@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 (
  python "%~dp0launch_local.py"
) else (
  start "" pythonw "%~dp0launch_local.py"
)
