@echo off
chcp 65001 >nul
cd /d "%~dp0"
python app\setup_local.py --install
if errorlevel 1 (
    echo 安装未完成，请查看上方提示。
    pause
    exit /b 1
)
echo 本地环境已准备好，以后双击“处理试卷.bat”即可。
pause
