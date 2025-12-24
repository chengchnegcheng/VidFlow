@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0\.."
title VidFlow - 优化构建
color 0B

echo.
echo ========================================
echo   VidFlow - 优化构建脚本
echo ========================================
echo.
echo 此脚本将执行以下优化：
echo   ✓ 清理所有缓存和旧构建
echo   ✓ 使用优化配置构建前端
echo   ✓ 使用优化配置打包后端
echo   ✓ 使用最大压缩打包 Electron
echo.
echo 预期效果：
echo   - 减少 100-200 MB 安装包体积
echo   - 移除调试信息和测试文件
echo   - 启用最大压缩
echo.

set /p confirm=确认开始优化构建？(Y/N):
if /i not "%confirm%"=="Y" (
    echo 已取消
    pause
    exit /b 0
)

echo.
echo ========================================
echo [1/5] 清理缓存和旧构建...
echo ========================================
echo.

if exist "backend\build" (
    echo 清理 backend\build...
    rmdir /S /Q "backend\build"
)

if exist "backend\dist" (
    echo 清理 backend\dist...
    rmdir /S /Q "backend\dist"
)

if exist "frontend\dist" (
    echo 清理 frontend\dist...
    rmdir /S /Q "frontend\dist"
)

if exist "dist-output" (
    echo 清理 dist-output...
    rmdir /S /Q "dist-output"
)

REM 清理 Python 缓存
echo 清理 Python 缓存...
for /d /r "backend" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
for /r "backend" %%f in (*.pyc *.pyo) do @if exist "%%f" del /q "%%f"

echo ✅ 清理完成
echo.

echo ========================================
echo [2/5] 检查版本号...
echo ========================================
echo.

REM 使用 PowerShell 读取版本号
set "CURRENT_VERSION="
for /f "delims=" %%v in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Host $json.version -NoNewline"') do set "CURRENT_VERSION=%%v"

if not defined CURRENT_VERSION (
    echo ❌ 无法读取版本号
    pause
    exit /b 1
)

echo 📦 当前版本: %CURRENT_VERSION%
echo.

echo ========================================
echo [3/5] 构建前端 (优化模式)...
echo ========================================
echo.

cd frontend
echo 设置生产环境变量...
set NODE_ENV=production

echo 开始构建...
call npm run build

if errorlevel 1 (
    echo ❌ 前端构建失败！
    cd ..
    pause
    exit /b 1
)

cd ..
echo ✅ 前端构建完成
echo.

REM 显示前端构建大小
echo 前端构建产物大小：
powershell -Command "$size = (Get-ChildItem -Path 'frontend\dist' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host \"  $([math]::Round($size,2)) MB\""
echo.

echo ========================================
echo [4/5] 打包后端 (优化模式)...
echo ========================================
echo.

cd backend

REM 检查虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo ❌ 虚拟环境不存在！
    echo 💡 请先运行 SETUP.bat 创建虚拟环境
    cd ..
    pause
    exit /b 1
)

echo 使用虚拟环境中的 Python...
venv\Scripts\python.exe --version
echo.

echo 开始打包（使用优化配置）...
venv\Scripts\python.exe -m PyInstaller backend.spec --clean --noconfirm --log-level=WARN

if errorlevel 1 (
    echo ❌ 后端打包失败！
    cd ..
    pause
    exit /b 1
)

cd ..
echo ✅ 后端打包完成
echo.

REM 显示后端打包大小
echo 后端打包产物大小：
powershell -Command "$size = (Get-ChildItem -Path 'backend\dist\VidFlow-Backend' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host \"  $([math]::Round($size,2)) MB\""
echo.

echo ========================================
echo [5/5] 打包 Electron (最大压缩)...
echo ========================================
echo.

echo 使用 electron-builder 打包...
call npm run build:electron

if errorlevel 1 (
    echo ❌ Electron 打包失败！
    pause
    exit /b 1
)

echo ✅ Electron 打包完成
echo.

echo ========================================
echo 🎉 优化构建完成！
echo ========================================
echo.

REM 显示最终安装包信息
if exist "dist-output" (
    echo 📦 安装包信息：
    echo.
    powershell -Command "Get-ChildItem -Path 'dist-output\*.exe' | ForEach-Object { Write-Host \"  文件名: $($_.Name)\"; Write-Host \"  大小: $([math]::Round($_.Length/1MB,2)) MB\"; Write-Host \"  路径: $($_.FullName)\"; Write-Host \"\" }"

    echo ========================================
    echo.
    echo 💡 提示：
    echo   - 安装包位于 dist-output 目录
    echo   - 已启用最大压缩
    echo   - 已移除调试信息和测试文件
    echo   - 已排除不必要的依赖
    echo.
) else (
    echo ⚠️ 未找到安装包文件
)

pause
exit /b 0
