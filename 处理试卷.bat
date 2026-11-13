@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 首次运行，正在准备本地环境……
    python app\setup_local.py --install
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" app\exam_print.py --open %*
if errorlevel 1 goto failed
echo.
echo 已完成。打印文件在 output\最新结果，核验通过的原文件在“已处理”。
echo 打印：A4 竖向，每张1页，双面长边翻转。
pause
exit /b 0
:failed
echo.
echo 有项目未完成，请查看上方提示。未通过核验的原文件仍在“待处理试卷”。
pause
exit /b 1
