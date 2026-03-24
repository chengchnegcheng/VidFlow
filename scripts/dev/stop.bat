@echo off
chcp 65001 >nul
title VidFlow Desktop - Stop Services
color 0C

cd /d "%~dp0\..\.."

echo.
echo ========================================
echo   VidFlow Desktop - Stop Services
echo ========================================
echo.

REM Try to get backend port from config
set BACKEND_PORT=
if exist "backend\data\backend_port.json" (
    for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "if (Test-Path 'backend\\data\\backend_port.json') { (Get-Content 'backend\\data\\backend_port.json' | ConvertFrom-Json).port }"`) do (
        set BACKEND_PORT=%%p
    )
)

set FRONTEND_PORT=
if exist "frontend_port.json" (
    for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "if (Test-Path 'frontend_port.json') { (Get-Content 'frontend_port.json' | ConvertFrom-Json).port }"`) do (
        set FRONTEND_PORT=%%p
    )
)
if not defined FRONTEND_PORT set FRONTEND_PORT=5173

REM Stop Python backend
echo [1/5] Stopping Python backend...
if defined BACKEND_PORT (
    echo       Checking port %BACKEND_PORT%...
    for /f "tokens=5" %%a in ('netstat -aon ^| find ":%BACKEND_PORT%" ^| find "LISTENING"') do (
        echo       Killing process %%a on port %BACKEND_PORT%
        taskkill /F /PID %%a >nul 2>&1
    )
)

REM Kill all Python processes (safer for VidFlow backend)
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo       Stopping all Python processes...
    taskkill /F /IM python.exe >nul 2>&1
    echo       [OK] Python processes stopped
) else (
    echo       [OK] No Python processes running
)

REM Stop Frontend dev server (dynamic port)
echo.
echo [2/5] Stopping Frontend dev server ^(port %FRONTEND_PORT%^)...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":%FRONTEND_PORT%" ^| find "LISTENING"') do (
    echo       Killing process %%a
    taskkill /F /PID %%a >nul 2>&1
)
echo       [OK] Frontend server stopped

REM Stop Electron
echo.
echo [3/5] Stopping Electron processes...
tasklist /FI "IMAGENAME eq electron.exe" 2>NUL | find /I "electron.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    taskkill /F /IM electron.exe >nul 2>&1
    echo       [OK] Electron stopped
) else (
    echo       [OK] No Electron processes running
)

REM Stop VidFlow.exe (if running packaged app)
echo.
echo [4/5] Stopping VidFlow packaged app...
tasklist /FI "IMAGENAME eq VidFlow.exe" 2>NUL | find /I "VidFlow.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    taskkill /F /IM VidFlow.exe >nul 2>&1
    echo       [OK] VidFlow app stopped
) else (
    echo       [OK] No VidFlow app running
)

REM Clean up port file
echo.
echo [5/5] Cleaning up...
if exist "backend\data\backend_port.json" (
    del /q "backend\data\backend_port.json" >nul 2>&1
    echo       [OK] Backend port file cleaned
)

REM Kill orphaned Node processes (be careful - only if spawned by our scripts)
REM Commented out to avoid killing user's other Node processes
REM taskkill /F /IM node.exe >nul 2>&1

echo.
color 0A
echo ========================================
echo   All VidFlow services stopped!
echo ========================================
echo.
echo   Backend: Stopped
echo   Frontend: Stopped
echo   Electron: Stopped
echo   Port file: Cleaned
echo.
echo You can now safely restart using start.bat
echo.
echo ========================================
echo.
pause
