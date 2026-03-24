@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0\.." || exit /b 1
set "ROOT_DIR=%CD%"
set "BUILD_LOG_DIR=%ROOT_DIR%\build-logs\optimized"
set "FRONTEND_LOG=%BUILD_LOG_DIR%\frontend-build.log"
set "BACKEND_LOG=%BUILD_LOG_DIR%\backend-build.log"
set "ELECTRON_LOG=%BUILD_LOG_DIR%\electron-build.log"
set "NO_COLOR=1"
set "FORCE_COLOR=0"
set "npm_config_color=false"
set "npm_config_unicode=false"

echo.
echo ========================================
echo   VidFlow - Optimized Build
echo ========================================
echo.
echo This script will:
echo   1. Clean caches and previous build outputs
echo   2. Build the frontend in production mode
echo   3. Build the backend with slim packaging options
echo   4. Build the Electron installer with maximum compression
echo.
echo Slim build options:
echo   - Skip bundling FFmpeg / ffprobe / yt-dlp
echo   - Skip bundling the Playwright Python package
echo   - Download these components on first use
echo.

if not defined confirm set /p "confirm=Continue? (Y/N): "
if /i not "%confirm%"=="Y" goto :cancel

set "VIDFLOW_BUNDLE_TOOLS=0"
set "VIDFLOW_BUNDLE_PLAYWRIGHT=0"

call :step "1/5" "Clean caches and old builds"
call :remove_dir "backend\build"
call :remove_dir "backend\dist"
call :remove_dir "frontend\dist"
call :remove_dir "dist-output"
call :remove_dir "%BUILD_LOG_DIR%"
mkdir "%BUILD_LOG_DIR%" >nul 2>&1

echo Cleaning Python cache...
for /d /r "backend" %%D in (__pycache__) do if exist "%%D" rmdir /s /q "%%D"
for /r "backend" %%F in (*.pyc *.pyo) do if exist "%%F" del /q "%%F"
echo Done.
echo Build logs: %BUILD_LOG_DIR%
echo.

call :step "2/5" "Read version"
call :read_version
if errorlevel 1 goto :version_error
echo Current version: %CURRENT_VERSION%
echo.
echo Slim packaging flags enabled:
echo   VIDFLOW_BUNDLE_TOOLS=0
echo   VIDFLOW_BUNDLE_PLAYWRIGHT=0
echo.

call :step "3/5" "Build frontend"
echo Writing log: %FRONTEND_LOG%
pushd frontend || goto :frontend_error
set "NODE_ENV=production"
call npm run build > "%FRONTEND_LOG%" 2>&1
set "BUILD_RC=%errorlevel%"
popd
if not "%BUILD_RC%"=="0" goto :frontend_error
echo Frontend build completed.
echo Frontend log: %FRONTEND_LOG%
call :print_dir_size "frontend\dist" "Frontend output"

call :step "4/5" "Build backend"
if not exist "backend\venv\Scripts\python.exe" goto :missing_venv
echo Using backend virtual environment:
backend\venv\Scripts\python.exe --version
echo.
echo Writing log: %BACKEND_LOG%
pushd backend || goto :backend_error
venv\Scripts\python.exe -m PyInstaller backend.spec --clean --noconfirm --log-level=WARN > "%BACKEND_LOG%" 2>&1
set "BUILD_RC=%errorlevel%"
popd
if not "%BUILD_RC%"=="0" goto :backend_error
echo Backend build completed.
echo Backend log: %BACKEND_LOG%
call :print_dir_size "backend\dist\VidFlow-Backend" "Backend output"

call :step "5/5" "Build Electron installer"
echo Writing log: %ELECTRON_LOG%
call npm run build:electron > "%ELECTRON_LOG%" 2>&1
set "BUILD_RC=%errorlevel%"
if not "%BUILD_RC%"=="0" goto :electron_error
echo Electron packaging completed.
echo Electron log: %ELECTRON_LOG%
echo.
echo ========================================
echo   Optimized build completed
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
    echo Removing %~1 ...
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
    echo %~2: not found
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
    echo No installer files were found in dist-output.
    echo.
    goto :eof
)
echo Installer files:
echo.
for %%F in (dist-output\*.exe) do call :print_artifact "%%~fF"
echo Notes:
echo   - Installers are stored in the dist-output directory
echo   - Maximum compression is enabled
echo   - FFmpeg, yt-dlp, and Playwright are installed on demand in this slim build
echo.
goto :eof

:print_artifact
set /a SIZE_MB=%~z1 / 1048576
echo File: %~nx1
echo Size: !SIZE_MB! MB
echo Path: %~f1
echo.
goto :eof

:missing_venv
echo Backend virtual environment not found: backend\venv\Scripts\python.exe
echo Run scripts\SETUP.bat first.
goto :abort

:version_error
echo Failed to read the version from package.json.
goto :abort

:frontend_error
echo Frontend build failed.
call :show_log_tail "%FRONTEND_LOG%"
goto :abort

:backend_error
echo Backend build failed.
call :show_log_tail "%BACKEND_LOG%"
goto :abort

:electron_error
echo Electron packaging failed.
call :show_log_tail "%ELECTRON_LOG%"
goto :abort

:cancel
echo Build cancelled.
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
echo Log file: %~1
echo Last 40 log lines:
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -LiteralPath '%~1' -Tail 40"
echo.
goto :eof
