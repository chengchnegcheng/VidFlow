@echo off
chcp 936 >nul
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0\..\.." || exit /b 1
set "ROOT_DIR=%CD%"
set "BUILD_LOG_DIR=%ROOT_DIR%\build-logs\optimized"
set "FRONTEND_LOG=%BUILD_LOG_DIR%\frontend-build.log"
set "BACKEND_LOG=%BUILD_LOG_DIR%\backend-build.log"
set "ELECTRON_LOG=%BUILD_LOG_DIR%\electron-build.log"
set "NO_COLOR=1"
set "FORCE_COLOR=0"
set "npm_config_color=false"
set "npm_config_unicode=false"
title VidFlow - 优化构建
color 0B

echo.
echo ========================================
echo   VidFlow - 优化构建
echo ========================================
echo.
echo 此脚本将执行以下操作：
echo   1. 清理缓存和上次构建产物
echo   2. 以生产模式构建前端
echo   3. 以精简打包选项构建后端
echo   4. 以最大压缩率打包 Electron 安装包
echo.
echo 精简构建选项：
echo   - 不内置 FFmpeg / ffprobe / yt-dlp
echo   - 不内置 Playwright Python 包
echo   - 以上组件将在首次使用时按需下载
echo.

if not defined confirm set /p "confirm=是否继续？(Y/N): "
if /i not "%confirm%"=="Y" goto :cancel

set "VIDFLOW_BUNDLE_TOOLS=0"
set "VIDFLOW_BUNDLE_PLAYWRIGHT=0"

call :step "1/5" "清理缓存和旧构建"
call :remove_dir "backend\build"
call :remove_dir "backend\dist"
call :remove_dir "frontend\dist"
call :remove_dir "dist-output"
call :remove_dir "%BUILD_LOG_DIR%"
mkdir "%BUILD_LOG_DIR%" >nul 2>&1

echo 正在清理 Python 缓存...
for /d /r "backend" %%D in (__pycache__) do if exist "%%D" rmdir /s /q "%%D"
for /r "backend" %%F in (*.pyc *.pyo) do if exist "%%F" del /q "%%F"
echo [完成] Python 缓存已清理。
echo 构建日志目录: %BUILD_LOG_DIR%
echo.

call :step "2/5" "读取版本号"
call :read_version
if errorlevel 1 goto :version_error
echo 当前版本: %CURRENT_VERSION%
echo.
echo 已启用精简打包参数：
echo   VIDFLOW_BUNDLE_TOOLS=0
echo   VIDFLOW_BUNDLE_PLAYWRIGHT=0
echo.

call :step "3/5" "构建前端"
echo 正在写入日志: %FRONTEND_LOG%
pushd frontend || goto :frontend_error
set "NODE_ENV=production"
call npm run build > "%FRONTEND_LOG%" 2>&1
set "BUILD_RC=%errorlevel%"
popd
if not "%BUILD_RC%"=="0" goto :frontend_error
echo [完成] 前端构建完成。
echo 前端日志: %FRONTEND_LOG%
call :print_dir_size "frontend\dist" "前端产物大小"

call :step "4/5" "构建后端"
if not exist "backend\venv\Scripts\python.exe" goto :missing_venv
echo 使用后端虚拟环境：
backend\venv\Scripts\python.exe --version
echo.
echo 正在写入日志: %BACKEND_LOG%
pushd backend || goto :backend_error
venv\Scripts\python.exe -m PyInstaller backend.spec --clean --noconfirm --log-level=WARN > "%BACKEND_LOG%" 2>&1
set "BUILD_RC=%errorlevel%"
popd
if not "%BUILD_RC%"=="0" goto :backend_error
echo [完成] 后端构建完成。
echo 后端日志: %BACKEND_LOG%
call :print_dir_size "backend\dist\VidFlow-Backend" "后端产物大小"

call :step "5/5" "打包 Electron 安装包"
echo 正在写入日志: %ELECTRON_LOG%
call npm run build:electron > "%ELECTRON_LOG%" 2>&1
set "BUILD_RC=%errorlevel%"
if not "%BUILD_RC%"=="0" goto :electron_error
echo [完成] Electron 打包完成。
echo Electron 日志: %ELECTRON_LOG%
echo.
echo ========================================
echo   优化构建完成
echo ========================================
echo.
call :print_artifacts
call :pause_if_needed
exit /b 0

:step
echo.
echo ========================================
echo [%~1] %~2
echo ========================================
echo.
goto :eof

:remove_dir
if exist "%~1" (
    echo 正在删除 %~1 ...
    rmdir /s /q "%~1"
)
goto :eof

:read_version
set "CURRENT_VERSION="
for /f "usebackq delims=" %%V in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; $json.version"`) do set "CURRENT_VERSION=%%V"
if not defined CURRENT_VERSION exit /b 1
exit /b 0

:print_dir_size
if not exist "%~1" (
    echo %~2: 未找到
    echo.
    goto :eof
)
set "SIZE_MB="
for /f "usebackq delims=" %%S in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$size = (Get-ChildItem -LiteralPath '%~1' -Recurse -File | Measure-Object Length -Sum).Sum / 1MB; [math]::Round($size, 2)"`) do set "SIZE_MB=%%S"
echo %~2: !SIZE_MB! MB
echo.
goto :eof

:print_artifacts
if not exist "dist-output\*.exe" (
    echo dist-output 中未找到安装包文件。
    echo.
    goto :eof
)
echo 安装包文件：
echo.
for %%F in (dist-output\*.exe) do call :print_artifact "%%~fF"
echo 说明：
echo   - 安装包位于 dist-output 目录
echo   - 已启用最大压缩率
echo   - 此精简构建会在首次使用时按需安装 FFmpeg、yt-dlp 和 Playwright
echo.
goto :eof

:print_artifact
set /a SIZE_MB=%~z1 / 1048576
echo 文件: %~nx1
echo 大小: !SIZE_MB! MB
echo 路径: %~f1
echo.
goto :eof

:missing_venv
echo [错误] 未找到后端虚拟环境: backend\venv\Scripts\python.exe
echo 请先运行 scripts\dev\setup.bat。
goto :abort

:version_error
echo [错误] 无法从 package.json 读取版本号。
goto :abort

:frontend_error
echo [错误] 前端构建失败。
call :show_log_tail "%FRONTEND_LOG%"
goto :abort

:backend_error
echo [错误] 后端构建失败。
call :show_log_tail "%BACKEND_LOG%"
goto :abort

:electron_error
echo [错误] Electron 打包失败。
call :show_log_tail "%ELECTRON_LOG%"
goto :abort

:cancel
echo 已取消构建。
call :pause_if_needed
exit /b 0

:abort
echo.
call :pause_if_needed
exit /b 1

:pause_if_needed
if /i not "%VIDFLOW_SKIP_PAUSE%"=="1" pause
goto :eof

:show_log_tail
if "%~1"=="" goto :eof
if not exist "%~1" goto :eof
echo 日志文件: %~1
echo 最近 40 行日志：
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -LiteralPath '%~1' -Tail 40"
echo.
goto :eof