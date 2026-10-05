@echo off
chcp 65001 >nul
echo ========================================
echo   实况照片合并器 - 打包脚本
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 安装 PyInstaller
echo [1/3] 安装 PyInstaller...
pip install pyinstaller Pillow -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

:: 打包
echo [2/3] 开始打包...
pyinstaller --noconfirm --onefile --windowed ^
    --name "LivePhotoCombiner" ^
    --hidden-import PIL ^
    main.py

if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

:: 完成
echo [3/3] 打包完成！
echo.
echo 可执行文件位置: dist\LivePhotoCombiner.exe
echo.
pause
