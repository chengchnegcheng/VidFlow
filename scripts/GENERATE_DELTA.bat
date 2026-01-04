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
echo 此脚本用于生成版本间的差异包
echo 需要在服务端运行，或将安装包上传到服务端后执行
echo.

REM 读取当前版本
for /f "delims=" %%v in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Host $json.version -NoNewline"') do set "TARGET_VERSION=%%v"

echo 📦 目标版本 (新版本): %TARGET_VERSION%
echo.

set /p SOURCE_VERSION=请输入源版本号 (旧版本，如 1.0.0): 

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
    echo      v%TARGET_VERSION%\
    echo        VidFlow-Backend\
    echo        frontend\dist\
    echo.
    pause
    exit /b 1
)

if not exist "%TARGET_DIR%" (
    echo ❌ 目标版本目录不存在: %TARGET_DIR%
    echo.
    echo 💡 请先将当前构建产物复制到 %TARGET_DIR%
    echo.
    pause
    exit /b 1
)

echo ========================================
echo 开始生成差异包...
echo ========================================
echo.

REM 调用 Python 脚本生成差异包
cd backend
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -c "from src.core.delta_generator import DeltaGenerator; from pathlib import Path; dg = DeltaGenerator(Path('../releases/deltas')); result = dg.generate_delta('%SOURCE_VERSION%', '%TARGET_VERSION%', Path('../%SOURCE_DIR%'), Path('../%TARGET_DIR%'), 'win32', 'x64'); print(f'✅ 差异包生成完成: {result.delta_path}')"
) else (
    echo ❌ Python 虚拟环境不存在
    cd ..
    pause
    exit /b 1
)

cd ..

echo.
echo ========================================
echo 🎉 差异包生成完成！
echo ========================================
echo.
echo 差异包位于: releases\deltas\
echo.
echo 下一步:
echo   1. 将差异包上传到更新服务器
echo   2. 在数据库中注册差异包信息
echo.

pause
exit /b 0
