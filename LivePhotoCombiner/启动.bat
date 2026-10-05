@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动实况照片合并器...
echo.
python main.py
if errorlevel 1 (
    echo.
    echo ========================================
    echo 程序运行出错，错误信息如上
    echo ========================================
    echo.
    pause
)
