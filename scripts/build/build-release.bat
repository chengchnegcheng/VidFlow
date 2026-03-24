@echo off
chcp 936 >nul
setlocal EnableExtensions

cd /d "%~dp0\..\.." || exit /b 1

:menu
cls
echo ===============================================
echo VidFlow 发布构建脚本
echo ===============================================
echo.
echo 请选择构建类型：
echo.
echo [1] 完整构建（后端 + 前端 + 打包）
echo [2] 仅构建后端
echo [3] 仅构建前端
echo [4] 仅打包 Electron
echo [5] 快速打包（不重新构建后端和前端）
echo [6] 查看构建产物
echo [7] 清理构建缓存
echo [0] 退出
echo.

set "choice="
set /p "choice=请输入选项 [0-7]: "

if "%choice%"=="1" goto build_all
if "%choice%"=="2" goto build_backend
if "%choice%"=="3" goto build_frontend
if "%choice%"=="4" goto build_electron
if "%choice%"=="5" goto package_only
if "%choice%"=="6" goto show_output
if "%choice%"=="7" goto clean
if "%choice%"=="0" goto end
goto menu

:build_all
echo.
echo ========================================
echo 开始完整发布构建...
echo ========================================
echo.

call :read_version
if errorlevel 1 (
    echo [错误] 无法从 package.json 读取版本号。
    call :pause_if_needed
    goto menu
)

echo [1/4] 当前版本：%CURRENT_VERSION%
set "confirm="
set /p "confirm=确认按此版本继续构建？(Y/N): "
if /i not "%confirm%"=="Y" goto menu

echo.
echo [2/4] 构建后端（PyInstaller）...
call :build_backend_step
if errorlevel 1 (
    call :pause_if_needed
    goto menu
)

echo.
echo [3/4] 构建前端（Vite）...
call :build_frontend_step
if errorlevel 1 (
    call :pause_if_needed
    goto menu
)

echo.
echo [4/4] 打包 Electron（electron-builder）...
call :build_electron_step
if errorlevel 1 (
    call :pause_if_needed
    goto menu
)

echo.
echo ========================================
echo 完整构建完成。
echo ========================================
echo 构建输出目录：dist-output
echo.
call :pause_if_needed
goto show_output

:build_backend
echo.
echo 开始构建后端...
call :build_backend_step
echo.
call :pause_if_needed
goto menu

:build_frontend
echo.
echo 开始构建前端...
call :build_frontend_step
echo.
call :pause_if_needed
goto menu

:build_electron
echo.
echo 开始打包 Electron...
call :build_electron_step
echo.
call :pause_if_needed
goto menu

:package_only
echo.
echo 使用现有构建结果快速打包...
call npm run package:win
if errorlevel 1 (
    echo [错误] 打包失败。
) else (
    echo [完成] 打包完成。
)
echo.
call :pause_if_needed
goto menu

:show_output
echo.
echo ========================================
echo 构建产物
echo ========================================
if exist "dist-output\*.exe" (
    dir /B "dist-output\*.exe"
    echo.
    echo 详细信息：
    dir "dist-output\*.exe"
) else (
    if exist "dist-output" (
        echo dist-output 目录中没有找到 .exe 文件。
    ) else (
        echo [错误] 未找到 dist-output 目录。
    )
)
echo.
call :pause_if_needed
goto menu

:clean
echo.
echo 正在清理构建缓存...
echo.
if exist "backend\build" (
    rmdir /S /Q "backend\build"
    echo [完成] 已删除 backend\build
)
if exist "backend\dist" (
    rmdir /S /Q "backend\dist"
    echo [完成] 已删除 backend\dist
)
if exist "frontend\dist" (
    rmdir /S /Q "frontend\dist"
    echo [完成] 已删除 frontend\dist
)
if exist "dist-output" (
    rmdir /S /Q "dist-output"
    echo [完成] 已删除 dist-output
)
echo.
echo 清理完成。
call :pause_if_needed
goto menu

:build_backend_step
if not exist "backend\venv\Scripts\python.exe" (
    echo [错误] 未找到后端虚拟环境。
    echo 请先运行 scripts\dev\setup.bat。
    exit /b 1
)

pushd backend || (
    echo [错误] 无法进入 backend 目录。
    exit /b 1
)

echo [信息] 使用后端虚拟环境：
venv\Scripts\python.exe --version
echo.
venv\Scripts\python.exe -m PyInstaller backend.spec --clean --noconfirm
set "build_rc=%errorlevel%"
popd

if not "%build_rc%"=="0" (
    echo [错误] 后端构建失败。
    exit /b 1
)

echo [完成] 后端构建完成。
exit /b 0

:build_frontend_step
pushd frontend || (
    echo [错误] 无法进入 frontend 目录。
    exit /b 1
)

call npm run build
set "build_rc=%errorlevel%"
popd

if not "%build_rc%"=="0" (
    echo [错误] 前端构建失败。
    exit /b 1
)

echo [完成] 前端构建完成。
exit /b 0

:build_electron_step
call npm run build:electron
if errorlevel 1 (
    echo [错误] Electron 打包失败。
    exit /b 1
)

echo [完成] Electron 打包完成。
exit /b 0

:read_version
set "CURRENT_VERSION="
for /f "usebackq delims=" %%V in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; $json.version"`) do set "CURRENT_VERSION=%%V"
if not defined CURRENT_VERSION exit /b 1
exit /b 0

:pause_if_needed
if /i not "%VIDFLOW_SKIP_PAUSE%"=="1" pause
exit /b 0

:end
echo.
echo 已退出发布构建脚本。
exit /b 0