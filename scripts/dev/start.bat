@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title VidFlow Desktop - Electron Mode
color 0A

cd /d "%~dp0\.."

echo.
echo ========================================
echo   VidFlow Desktop - Starting
echo ========================================
echo.

REM Clean old backend port file
if exist "backend\data\backend_port.json" (
    del /q "backend\data\backend_port.json" >nul 2>&1
)

REM Start backend with random port
echo [1/3] Starting Python backend...
start "VidFlow Backend" cmd /k "cd /d "%~dp0\..\backend" && venv\Scripts\activate && set PYTHONPATH=%CD% && python -m src.main"
echo [INFO] Backend will use random port

REM Wait for backend to become healthy before Electron tries to reuse it
echo [WAIT] Waiting for backend to become healthy...
set BACKEND_PORT=
for /l %%i in (1,1,40) do (
    if exist "backend\data\backend_port.json" (
        for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "try { $cfg = Get-Content 'backend\\data\\backend_port.json' | ConvertFrom-Json; if ($cfg.port) { $resp = Invoke-WebRequest -Uri ('http://127.0.0.1:' + $cfg.port + '/health') -UseBasicParsing -TimeoutSec 2; if ($resp.StatusCode -eq 200) { Write-Output $cfg.port } } } catch {}"`) do (
            set BACKEND_PORT=%%p
        )
        if defined BACKEND_PORT goto :backend_ready
    )
    timeout /t 1 >nul
)

:backend_ready
if defined BACKEND_PORT (
    echo [OK] Backend ready on port !BACKEND_PORT!
) else (
    color 0E
    echo [WARN] Backend did not report healthy in time. Electron will still try to reuse the existing dev backend.
)

echo.
REM Clean old frontend port file to force rewrite
if exist "frontend_port.json" (
    del /q "frontend_port.json" >nul 2>&1
)

echo [2/3] Starting frontend dev server...
start "VidFlow Frontend" cmd /k "cd /d "%~dp0\..\frontend" && npm run dev"
echo [WAIT] Waiting for frontend to write port file...
for /l %%i in (1,1,30) do (
    if exist "frontend_port.json" goto :frontend_ready
    timeout /t 1 >nul
)

:frontend_ready
if not exist "frontend_port.json" (
    color 0C
    echo [WARN] Frontend port file not found. Electron may fail to load UI.
) else (
    echo [OK] Frontend port detected
)

echo.
echo [3/3] Starting Electron Desktop App...
timeout /t 2 >nul

REM Start Electron
start "VidFlow Electron" "%~dp0START_ELECTRON_DEV.bat"

echo.
color 0A
echo ========================================
echo   VidFlow Desktop Started!
echo ========================================
echo.
echo   Mode: Electron Desktop App
if defined BACKEND_PORT (
    echo   Backend: Existing dev backend on http://127.0.0.1:!BACKEND_PORT!
) else (
    echo   Backend: Existing dev backend - port pending
)
call :get_frontend_port
echo   Frontend: http://localhost:%FRONTEND_PORT%
echo.
echo   The desktop window will open automatically.
echo   Electron will reuse the backend started above.
echo.
echo ========================================
echo.
echo To stop: Close the command windows
echo.
pause

goto :eof

:get_frontend_port
set FRONTEND_PORT=
if exist "frontend_port.json" (
    for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "if (Test-Path 'frontend_port.json') { (Get-Content 'frontend_port.json' | ConvertFrom-Json).port }"`) do (
        set FRONTEND_PORT=%%p
    )
)
if not defined FRONTEND_PORT set FRONTEND_PORT=5173
exit /b 0
