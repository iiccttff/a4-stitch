@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "output\最新结果" (
    start "" "output\最新结果"
) else (
    echo 还没有本次处理结果，请先双击“处理试卷.bat”。
    pause
)
