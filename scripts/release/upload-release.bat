@echo off
chcp 936 >nul
setlocal

cd /d "%~dp0\..\.."
title VidFlow - 发布上传
color 0A

for /f "delims=" %%v in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Host $json.version -NoNewline"') do set "VERSION=%%v"

echo.
echo ========================================
echo   VidFlow - 发布上传脚本
echo ========================================
echo.
echo [信息] 当前版本: %VERSION%
echo.

set "INSTALLER_PATH=dist-output\VidFlow-Setup-%VERSION%.exe"
if not exist "%INSTALLER_PATH%" (
    set "INSTALLER_PATH=dist-output\VidFlow Setup %VERSION%.exe"
)

if not exist "%INSTALLER_PATH%" (
    echo [错误] 未找到安装包。
    echo [信息] 请先运行 scripts\build\build-release.bat 或 npm run build 进行构建。
    echo.
    dir dist-output\*.exe 2>nul
    pause
    exit /b 1
)

echo [信息] 安装包: %INSTALLER_PATH%
for %%f in ("%INSTALLER_PATH%") do set "INSTALLER_FILE_NAME=%%~nxf"
echo.
echo [信息] 正在计算安装包哈希...
for /f "delims=" %%h in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -Path '%INSTALLER_PATH%' -Algorithm SHA512).Hash.ToLower()"') do set "FILE_HASH=%%h"
for /f "delims=" %%s in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Item '%INSTALLER_PATH%').Length"') do set "FILE_SIZE=%%s"

echo [信息] SHA-512: %FILE_HASH:~0,32%...
echo [信息] 大小: %FILE_SIZE% bytes
echo.
echo ========================================
echo 上传选项
echo ========================================
echo.
echo [1] 上传到更新服务器（手动）
echo [2] 生成发布元数据 JSON
echo [3] 同步到本地 releases 目录
echo [0] 退出
echo.

set /p choice=请选择操作: 

if "%choice%"=="1" goto upload_server
if "%choice%"=="2" goto generate_json
if "%choice%"=="3" goto copy_local
goto end

:upload_server
echo.
echo [信息] 上传到更新服务器
echo.
echo [信息] 请先配置好服务器凭据，然后手动上传安装包。
echo [信息] 示例:
echo   scp "%INSTALLER_PATH%" user@shcrystal.top:/path/to/releases/v%VERSION%/
echo.
pause
goto end

:generate_json
echo.
echo [信息] 正在生成发布元数据...
set "JSON_FILE=dist-output\release-%VERSION%.json"

(
echo {
echo   "version": "%VERSION%",
echo   "platform": "win32",
echo   "arch": "x64",
echo   "file_name": "%INSTALLER_FILE_NAME%",
echo   "file_size": %FILE_SIZE%,
echo   "file_hash": "%FILE_HASH%",
echo   "download_url": "https://shcrystal.top:8321/releases/v%VERSION%/%INSTALLER_FILE_NAME%",
echo   "release_notes": "",
echo   "is_mandatory": false,
echo   "channel": "stable"
echo }
) > "%JSON_FILE%"

echo.
echo [完成] 元数据已生成: %JSON_FILE%
echo.
type "%JSON_FILE%"
echo.
pause
goto end

:copy_local
echo.
echo [信息] 正在同步当前构建产物到 releases\v%VERSION% ...
echo [信息] 为避免旧文件影响增量包生成，将覆盖已有快照。
node scripts\release\archive-release.js --version=%VERSION%
if errorlevel 1 (
    echo.
    echo [错误] 同步本地发布快照失败。
    pause
    goto end
)
echo.
echo [信息] 现在可以运行 scripts\release\generate-delta.bat 或 npm run delta -- sourceVersion
echo.
pause
goto end

:end
echo.
echo 已退出。
exit /b 0