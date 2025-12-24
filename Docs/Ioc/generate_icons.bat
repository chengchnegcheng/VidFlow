@echo off
chcp 65001 >nul
echo 🎨 VidFlow Desktop 图标生成器
echo ========================================

REM 检查是否存在 SVG 文件
if not exist "icon.svg" (
    echo ❌ 未找到 icon.svg 文件
    pause
    exit /b 1
)

REM 检查 Python 是否安装
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python
    echo 请安装 Python: https://python.org/
    pause
    exit /b 1
)

echo ✓ 找到 Python
echo 📦 正在安装必要的依赖包...

REM 安装 Python 依赖
pip install Pillow cairosvg

if %errorlevel% neq 0 (
    echo ❌ 依赖安装失败
    echo 请手动运行: pip install Pillow cairosvg
    pause
    exit /b 1
)

echo ✓ 依赖安装完成
echo 🚀 开始生成图标...

REM 运行 Python 脚本
python generate_icons.py

echo.
echo 按任意键退出...
pause >nul