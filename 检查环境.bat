@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app\setup_local.py --check
) else (
    python app\setup_local.py --check
)
pause
