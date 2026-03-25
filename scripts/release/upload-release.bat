@echo off
chcp 936 >nul
setlocal EnableExtensions

cd /d "%~dp0\..\.." || exit /b 1
title VidFlow - 发布上传
color 0A

call :read_version
if errorlevel 1 goto fail
call :resolve_installer
if errorlevel 1 goto fail
call :compute_installer_info
if errorlevel 1 goto fail

set "NONINTERACTIVE=0"
if defined VIDFLOW_UPLOAD_ACTION set "NONINTERACTIVE=1"

if "%NONINTERACTIVE%"=="1" goto noninteractive

:menu
cls
echo.
echo ========================================
echo   VidFlow - 发布上传脚本
echo ========================================
echo.
call :print_summary
echo [1] 自动上传当前版本安装包到后台
echo [2] 自动上传指定源版本的增量包到后台
echo [3] 自动上传安装包和指定源版本增量包
echo [4] 生成发布元数据 JSON
echo [5] 同步到本地 releases 目录
echo [0] 退出
echo.

set "choice="
set /p "choice=请选择操作: "
echo.

if "%choice%"=="0" goto end
call :run_action "%choice%"
call :pause_if_needed
goto menu

:noninteractive
echo.
echo ========================================
echo   VidFlow - 发布上传脚本
echo ========================================
echo.
call :print_summary
echo [信息] 非交互模式，执行操作: %VIDFLOW_UPLOAD_ACTION%
echo.
call :run_action "%VIDFLOW_UPLOAD_ACTION%"
exit /b %ERRORLEVEL%

:print_summary
echo [信息] 当前版本: %VERSION%
echo [信息] 安装包: %INSTALLER_PATH%
echo [信息] 架构: %ARCH%
echo [信息] 大小: %FILE_SIZE% bytes
echo [信息] SHA-512: %FILE_HASH:~0,32%...
echo.
exit /b 0

:run_action
set "choice=%~1"
if "%choice%"=="1" goto run_action_1
if "%choice%"=="2" goto run_action_2
if "%choice%"=="3" goto run_action_3
if "%choice%"=="4" goto run_action_4
if "%choice%"=="5" goto run_action_5
echo [错误] 无效的操作: %choice%
exit /b 1

:run_action_1
call :upload_version_only
exit /b %ERRORLEVEL%

:run_action_2
call :upload_delta_only
exit /b %ERRORLEVEL%

:run_action_3
call :upload_all
exit /b %ERRORLEVEL%

:run_action_4
call :generate_json
exit /b %ERRORLEVEL%

:run_action_5
call :copy_local
exit /b %ERRORLEVEL%

:upload_version_only
call :ensure_admin_config
if errorlevel 1 exit /b 1
call :login_admin
if errorlevel 1 exit /b 1
call :upload_version
exit /b %ERRORLEVEL%

:upload_delta_only
call :resolve_delta_for_prompt
if errorlevel 1 exit /b 1
call :ensure_admin_config
if errorlevel 1 exit /b 1
call :login_admin
if errorlevel 1 exit /b 1
call :upload_delta
exit /b %ERRORLEVEL%

:upload_all
call :resolve_delta_for_prompt
if errorlevel 1 exit /b 1
call :ensure_admin_config
if errorlevel 1 exit /b 1
call :login_admin
if errorlevel 1 exit /b 1
call :upload_version
if errorlevel 1 exit /b 1
call :upload_delta
exit /b %ERRORLEVEL%

:generate_json
echo [信息] 正在生成发布元数据...
set "JSON_FILE=dist-output\release-%VERSION%.json"
call :resolve_download_base
if errorlevel 1 exit /b 1

(
echo {
echo   "version": "%VERSION%",
echo   "platform": "win32",
echo   "arch": "%ARCH%",
echo   "file_name": "%INSTALLER_FILE_NAME%",
echo   "file_size": %FILE_SIZE%,
echo   "file_hash": "%FILE_HASH%",
echo   "download_url": "%DOWNLOAD_BASE%/updates/files/v%VERSION%/%INSTALLER_FILE_NAME%",
echo   "release_notes": "",
echo   "is_mandatory": false,
echo   "channel": "stable"
echo }
) > "%JSON_FILE%"
if errorlevel 1 (
    echo [错误] 元数据生成失败。
    exit /b 1
)

echo.
echo [完成] 元数据已生成: %JSON_FILE%
echo.
type "%JSON_FILE%"
echo.
exit /b 0

:copy_local
echo [信息] 正在同步当前构建产物到 releases\v%VERSION% ...
echo [信息] 为避免旧文件影响增量包生成，将覆盖已有快照。
node scripts\release\archive-release.js --version=%VERSION%
if errorlevel 1 (
    echo.
    echo [错误] 同步本地发布快照失败。
    exit /b 1
)
echo.
echo [信息] 现在可以运行 scripts\release\generate-delta.bat ^<源版本号^> 或 npm run delta -- ^<sourceVersion^>
echo.
exit /b 0

:read_version
set "VERSION="
for /f "usebackq delims=" %%v in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Host $json.version -NoNewline"`) do set "VERSION=%%v"
if not defined VERSION (
    echo [错误] 无法读取 package.json 中的版本号。
    exit /b 1
)
exit /b 0

:resolve_installer
set "INSTALLER_PATH=dist-output\VidFlow-Setup-%VERSION%.exe"
if not exist "%INSTALLER_PATH%" set "INSTALLER_PATH=dist-output\VidFlow Setup %VERSION%.exe"
if not exist "%INSTALLER_PATH%" (
    echo [错误] 未找到安装包。
    echo [信息] 请先运行 scripts\build\build-release.bat 或 npm run build 进行构建。
    echo.
    dir dist-output\*.exe 2>nul
    exit /b 1
)
for %%f in ("%INSTALLER_PATH%") do set "INSTALLER_FILE_NAME=%%~nxf"
exit /b 0

:compute_installer_info
set "FILE_HASH="
set "FILE_SIZE="
set "ARCH="
for /f "usebackq delims=" %%h in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -Path '%INSTALLER_PATH%' -Algorithm SHA512).Hash.ToLower()"`) do set "FILE_HASH=%%h"
for /f "usebackq delims=" %%s in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Item '%INSTALLER_PATH%').Length"`) do set "FILE_SIZE=%%s"
for /f "usebackq delims=" %%a in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$fs=[System.IO.File]::OpenRead('%INSTALLER_PATH%'); try { $br=New-Object System.IO.BinaryReader($fs); if($br.ReadUInt16() -ne 0x5A4D){exit 0}; $fs.Position=0x3C; $peOffset=$br.ReadUInt32(); $fs.Position=$peOffset+4; $machine=$br.ReadUInt16(); switch($machine){ 0x8664 { 'x64' }; 0x014c { 'x32' }; 0xAA64 { 'arm64' }; default { '' } } } finally { $fs.Dispose() }"`) do set "ARCH=%%a"
if not defined ARCH set "ARCH=x64"
if not defined FILE_HASH exit /b 1
if not defined FILE_SIZE exit /b 1
exit /b 0

:resolve_delta_for_prompt
set "SOURCE_VERSION=%VIDFLOW_SOURCE_VERSION%"
if not defined SOURCE_VERSION (
    if "%NONINTERACTIVE%"=="1" (
        echo [错误] 非交互模式需要设置 VIDFLOW_SOURCE_VERSION。
        exit /b 1
    )
    set /p "SOURCE_VERSION=请输入源版本号 (例如 1.0.0): "
)
if not defined SOURCE_VERSION (
    echo [错误] 未输入源版本号。
    exit /b 1
)
call :resolve_delta_path
exit /b %ERRORLEVEL%

:resolve_delta_path
set "DELTA_PATH=releases\deltas\delta-%SOURCE_VERSION%-to-%VERSION%-win32-%ARCH%.zip"
if exist "%DELTA_PATH%" (
    for %%f in ("%DELTA_PATH%") do set "DELTA_FILE_NAME=%%~nxf"
    echo [信息] 增量包: %DELTA_PATH%
    exit /b 0
)

set "DELTA_PATH="
set "DELTA_FILE_NAME="
for /f "delims=" %%f in ('dir /b /a-d "releases\deltas\delta-%SOURCE_VERSION%-to-%VERSION%-win32-*.zip" 2^>nul') do (
    if not defined DELTA_PATH (
        set "DELTA_PATH=releases\deltas\%%f"
        set "DELTA_FILE_NAME=%%f"
    ) else (
        echo [错误] 找到多个候选增量包，请手动清理后再重试。
        dir /b "releases\deltas\delta-%SOURCE_VERSION%-to-%VERSION%-win32-*.zip" 2^>nul
        exit /b 1
    )
)

if not defined DELTA_PATH (
    echo [错误] 未找到源版本 %SOURCE_VERSION% 到目标版本 %VERSION% 的增量包。
    echo [信息] 请先运行 scripts\release\generate-delta.bat %SOURCE_VERSION%
    exit /b 1
)

echo [信息] 增量包: %DELTA_PATH%
exit /b 0

:ensure_admin_config
if not defined VIDFLOW_ADMIN_URL (
    if "%NONINTERACTIVE%"=="1" (
        echo [错误] 非交互模式需要设置 VIDFLOW_ADMIN_URL。
        exit /b 1
    )
    set /p "VIDFLOW_ADMIN_URL=请输入后台地址 (例如 http://127.0.0.1:8321 或 http://127.0.0.1:8321/admin): "
)
if not defined VIDFLOW_ADMIN_USERNAME (
    if "%NONINTERACTIVE%"=="1" (
        echo [错误] 非交互模式需要设置 VIDFLOW_ADMIN_USERNAME。
        exit /b 1
    )
    set /p "VIDFLOW_ADMIN_USERNAME=请输入后台用户名: "
)
if not defined VIDFLOW_ADMIN_PASSWORD (
    if "%NONINTERACTIVE%"=="1" (
        echo [错误] 非交互模式需要设置 VIDFLOW_ADMIN_PASSWORD。
        exit /b 1
    )
    set /p "VIDFLOW_ADMIN_PASSWORD=请输入后台密码: "
)

if not defined VIDFLOW_ADMIN_URL (
    echo [错误] 后台地址不能为空。
    exit /b 1
)
if not defined VIDFLOW_ADMIN_USERNAME (
    echo [错误] 后台用户名不能为空。
    exit /b 1
)
if not defined VIDFLOW_ADMIN_PASSWORD (
    echo [错误] 后台密码不能为空。
    exit /b 1
)

call :normalize_admin_base_url
exit /b %ERRORLEVEL%

:normalize_admin_base_url
set "ADMIN_BASE_URL="
for /f "usebackq delims=" %%u in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$u = $env:VIDFLOW_ADMIN_URL.Trim(); $u = $u.TrimEnd('/'); if ($u.ToLower().EndsWith('/admin')) { $u = $u.Substring(0, $u.Length - 6) }; Write-Host $u -NoNewline"`) do set "ADMIN_BASE_URL=%%u"
if not defined ADMIN_BASE_URL (
    echo [错误] 无法解析后台地址。
    exit /b 1
)
exit /b 0

:resolve_download_base
if not defined VIDFLOW_ADMIN_URL goto resolve_download_base_default
call :normalize_admin_base_url
if errorlevel 1 exit /b 1
set "DOWNLOAD_BASE=%ADMIN_BASE_URL%"
exit /b 0

:resolve_download_base_default
set "DOWNLOAD_BASE=http://127.0.0.1:8321"
exit /b 0

:login_admin
set "ADMIN_TOKEN="
for /f "usebackq delims=" %%t in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $body = @{ username = $env:VIDFLOW_ADMIN_USERNAME; password = $env:VIDFLOW_ADMIN_PASSWORD } | ConvertTo-Json; $login = Invoke-RestMethod -Uri ($env:ADMIN_BASE_URL + '/api/v1/admin/auth/login') -Method Post -ContentType 'application/json' -Body $body; Write-Host $login.access_token -NoNewline"`) do set "ADMIN_TOKEN=%%t"
if not defined ADMIN_TOKEN (
    echo [错误] 登录后台失败。
    exit /b 1
)
echo [信息] 登录成功。
exit /b 0

:upload_version
echo [信息] 正在上传正式包...
set "UPLOAD_VERSION_RESPONSE=%TEMP%\vidflow-upload-version-%RANDOM%.json"
curl.exe --fail-with-body -sS -X POST "%ADMIN_BASE_URL%/api/v1/admin/versions/upload" -H "Authorization: Bearer %ADMIN_TOKEN%" -F "file=@%INSTALLER_PATH%" -F "version=%VERSION%" -F "channel=stable" -F "platform=win32" -F "arch=%ARCH%" -F "release_notes=VidFlow %VERSION%" -F "is_mandatory=false" -F "rollout_percentage=100" > "%UPLOAD_VERSION_RESPONSE%"
if errorlevel 1 (
    echo [错误] 正式包上传失败。
    call :print_utf8_file "%UPLOAD_VERSION_RESPONSE%"
    del /q "%UPLOAD_VERSION_RESPONSE%" >nul 2>&1
    exit /b 1
)
echo [完成] 正式包上传成功。
call :print_utf8_file "%UPLOAD_VERSION_RESPONSE%"
del /q "%UPLOAD_VERSION_RESPONSE%" >nul 2>&1
exit /b 0

:upload_delta
echo [信息] 正在上传增量包...
set "UPLOAD_DELTA_RESPONSE=%TEMP%\vidflow-upload-delta-%RANDOM%.json"
curl.exe --fail-with-body -sS -X POST "%ADMIN_BASE_URL%/api/v1/admin/deltas/upload" -H "Authorization: Bearer %ADMIN_TOKEN%" -F "file=@%DELTA_PATH%" -F "source_version=%SOURCE_VERSION%" -F "target_version=%VERSION%" -F "platform=win32" -F "arch=%ARCH%" -F "full_size=%FILE_SIZE%" -F "manifest={}" > "%UPLOAD_DELTA_RESPONSE%"
if errorlevel 1 (
    echo [错误] 增量包上传失败。
    call :print_utf8_file "%UPLOAD_DELTA_RESPONSE%"
    del /q "%UPLOAD_DELTA_RESPONSE%" >nul 2>&1
    exit /b 1
)
echo [完成] 增量包上传成功。
call :print_utf8_file "%UPLOAD_DELTA_RESPONSE%"
del /q "%UPLOAD_DELTA_RESPONSE%" >nul 2>&1
exit /b 0

:print_utf8_file
set "UTF8_FILE=%~1"
if not exist "%UTF8_FILE%" exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -Command "$path = $env:UTF8_FILE; if (Test-Path -LiteralPath $path) { $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8; Write-Host $text -NoNewline }"
echo.
exit /b 0

:pause_if_needed
if /i not "%VIDFLOW_SKIP_PAUSE%"=="1" pause
exit /b 0

:fail
echo.
echo [错误] 发布上传脚本初始化失败。
call :pause_if_needed
exit /b 1

:end
echo.
echo 已退出。
exit /b 0