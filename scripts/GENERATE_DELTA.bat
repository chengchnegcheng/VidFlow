@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0\.."
title VidFlow - 生成增量更新包
color 0E

echo.
echo ========================================
echo   VidFlow - 增量更新包生成脚本
echo ========================================
echo.

REM 读取当前版本
for /f "delims=" %%v in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Host $json.version -NoNewline"') do set "TARGET_VERSION=%%v"

echo 📦 目标版本 (新版本): %TARGET_VERSION%
echo.

REM 列出可用的源版本
echo 可用的源版本:
for /d %%d in (releases\v*) do (
    set "ver=%%~nxd"
    set "ver=!ver:v=!"
    if not "!ver!"=="%TARGET_VERSION%" (
        echo   - !ver!
    )
)
echo.

set /p SOURCE_VERSION=请输入源版本号 (旧版本，如 1.0.2): 

if "%SOURCE_VERSION%"=="" (
    echo ❌ 源版本号不能为空
    pause
    exit /b 1
)

echo.
echo 将生成差异包: %SOURCE_VERSION% → %TARGET_VERSION%
echo.

REM 检查源版本目录是否存在
set "SOURCE_DIR=releases\v%SOURCE_VERSION%"
set "TARGET_DIR=releases\v%TARGET_VERSION%"

if not exist "%SOURCE_DIR%" (
    echo ❌ 源版本目录不存在: %SOURCE_DIR%
    echo.
    echo 💡 请确保以下目录结构存在:
    echo    releases\
    echo      v%SOURCE_VERSION%\
    echo        VidFlow-Backend\
    echo        frontend\dist\
    echo.
    pause
    exit /b 1
)

if not exist "%TARGET_DIR%" (
    echo ❌ 目标版本目录不存在: %TARGET_DIR%
    echo.
    echo 💡 请先运行 UPLOAD_RELEASE.bat 选择 [3] 复制到本地发布目录
    echo.
    pause
    exit /b 1
)

REM 确保输出目录存在
if not exist "releases\deltas" mkdir "releases\deltas"

echo ========================================
echo 开始生成差异包...
echo ========================================
echo.

REM 调用 Python 脚本生成差异包（从项目根目录运行）
if exist "backend\venv\Scripts\python.exe" (
    backend\venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend'); from pathlib import Path; from src.core.delta_generator import DeltaGenerator; g = DeltaGenerator(Path('releases/deltas')); r = g.generate_delta('%SOURCE_VERSION%', '%TARGET_VERSION%', Path('%SOURCE_DIR%'), Path('%TARGET_DIR%'), 'win32', 'x64'); print(f'Delta: {r.delta_path}')"
    if errorlevel 1 (
        echo.
        echo ❌ 差异包生成失败
        pause
        exit /b 1
    )
) else (
    echo ❌ Python 虚拟环境不存在
    echo 💡 请先运行: cd backend ^&^& python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo ========================================
echo 🎉 差异包生成完成！
echo ========================================
echo.
echo 差异包位于: releases\deltas\
echo.

REM 显示生成的文件
echo 生成的文件:
dir /b "releases\deltas\delta-%SOURCE_VERSION%-to-%TARGET_VERSION%-*.zip" 2>nul

echo.
echo 下一步:
echo   1. 登录更新服务器管理后台
echo   2. 进入「增量更新」标签页
echo   3. 上传差异包文件
echo.

pause
exit /b 0
