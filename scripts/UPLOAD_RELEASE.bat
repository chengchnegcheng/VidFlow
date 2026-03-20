@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0\.."
title VidFlow - 上传发布版本
color 0A

echo.
echo ========================================
echo   VidFlow - 发布版本上传脚本
echo ========================================
echo.

REM 读取当前版本
for /f "delims=" %%v in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Host $json.version -NoNewline"') do set "VERSION=%%v"

echo 📦 当前版本: %VERSION%
echo.

REM 检查安装包是否存在
set "INSTALLER_PATH=dist-output\VidFlow-Setup-%VERSION%.exe"
if not exist "%INSTALLER_PATH%" (
    set "INSTALLER_PATH=dist-output\VidFlow Setup %VERSION%.exe"
)

if not exist "%INSTALLER_PATH%" (
    echo ❌ 安装包不存在！
    echo 💡 请先运行 BUILD_OPTIMIZED.bat 或 BUILD_RELEASE.bat
    echo.
    dir dist-output\*.exe 2>nul
    pause
    exit /b 1
)

echo 📁 安装包: %INSTALLER_PATH%
echo.

REM 计算文件哈希
echo 计算文件哈希...
for /f "delims=" %%h in ('powershell -Command "(Get-FileHash -Path '%INSTALLER_PATH%' -Algorithm SHA512).Hash.ToLower()"') do set "FILE_HASH=%%h"
echo 📝 SHA-512: %FILE_HASH:~0,32%...
echo.

REM 获取文件大小
for /f "delims=" %%s in ('powershell -Command "(Get-Item '%INSTALLER_PATH%').Length"') do set "FILE_SIZE=%%s"
echo 📊 文件大小: %FILE_SIZE% bytes
echo.

echo ========================================
echo 上传选项
echo ========================================
echo.
echo [1] 上传到更新服务器 (shcrystal.top:8321)
echo [2] 仅生成发布信息 (JSON)
echo [3] 复制到本地发布目录
echo [0] 取消
echo.

set /p choice=请选择:

if "%choice%"=="1" goto upload_server
if "%choice%"=="2" goto generate_json
if "%choice%"=="3" goto copy_local
if "%choice%"=="0" goto end
goto end

:upload_server
echo.
echo 上传到更新服务器...
echo.
echo ⚠️ 此功能需要配置服务器凭据
echo 💡 建议使用 SCP 或 SFTP 手动上传
echo.
echo 上传命令示例:
echo   scp "%INSTALLER_PATH%" user@shcrystal.top:/path/to/releases/v%VERSION%/
echo.
pause
goto end

:generate_json
echo.
echo 生成发布信息...

set "JSON_FILE=dist-output\release-%VERSION%.json"

echo {> "%JSON_FILE%"
echo   "version": "%VERSION%",>> "%JSON_FILE%"
echo   "platform": "win32",>> "%JSON_FILE%"
echo   "arch": "x64",>> "%JSON_FILE%"
echo   "file_name": "VidFlow-Setup-%VERSION%.exe",>> "%JSON_FILE%"
echo   "file_size": %FILE_SIZE%,>> "%JSON_FILE%"
echo   "file_hash": "%FILE_HASH%",>> "%JSON_FILE%"
echo   "download_url": "http://shcrystal.top:8321/releases/v%VERSION%/VidFlow-Setup-%VERSION%.exe",>> "%JSON_FILE%"
echo   "release_notes": "",>> "%JSON_FILE%"
echo   "is_mandatory": false,>> "%JSON_FILE%"
echo   "channel": "stable">> "%JSON_FILE%"
echo }>> "%JSON_FILE%"

echo.
echo ✅ 发布信息已生成: %JSON_FILE%
echo.
type "%JSON_FILE%"
echo.
pause
goto end

:copy_local
echo.
echo 复制到本地发布目录...

set "RELEASE_DIR=releases\v%VERSION%"
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"

copy "%INSTALLER_PATH%" "%RELEASE_DIR%\"
echo ✅ 已复制到: %RELEASE_DIR%\
echo.

REM 同时复制构建产物用于生成差异包
echo 复制构建产物用于差异包生成...
if exist "backend\dist\VidFlow-Backend" (
    xcopy /E /I /Y "backend\dist\VidFlow-Backend" "%RELEASE_DIR%\VidFlow-Backend\"
)
if exist "frontend\dist" (
    xcopy /E /I /Y "frontend\dist" "%RELEASE_DIR%\frontend\dist\"
)

echo ✅ 构建产物已复制
echo.
echo 💡 现在可以运行 GENERATE_DELTA.bat 生成差异包
echo.
pause
goto end

:end
echo.
echo 退出
exit /b 0
