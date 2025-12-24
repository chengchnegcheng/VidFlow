@echo off
title VidFlow Desktop - Status Check

REM Switch to project root directory
cd /d "%~dp0.."

echo.
echo   VidFlow Desktop - Status Check
echo ========================================
echo.

REM Check Node.js
echo [Check] Node.js...
node --version 2>nul
if errorlevel 1 (
    echo [FAIL] Node.js not found
) else (
    echo [OK] Node.js installed
)

echo.

REM Check Python
echo [Check] Python...
python --version 2>nul
if errorlevel 1 (
    echo [FAIL] Python not found
) else (
    echo [OK] Python installed
)

echo.

REM Check npm
echo [Check] npm...
npm --version 2>nul
if errorlevel 1 (
    echo [FAIL] npm not found
) else (
    echo [OK] npm installed
)

echo.

REM Check Backend Service
echo [Check] Backend Service ^(http://localhost:8000^)...
curl -s http://localhost:8000/ >nul 2>&1
if errorlevel 1 (
    echo [NOT RUNNING] Backend not responding
) else (
    echo [RUNNING] Backend is running
)

echo.

REM Check Frontend Service
echo [Check] Frontend Service ^(http://localhost:5174^)...
curl -s http://localhost:5174/ >nul 2>&1
if errorlevel 1 (
    echo [NOT RUNNING] Frontend not responding
) else (
    echo [RUNNING] Frontend is running
)

echo.

REM Check node_modules
echo [Check] Dependencies...
if exist "node_modules" (
    echo [OK] Root dependencies installed
) else (
    echo [MISSING] Root dependencies not installed
    echo         Run: INSTALL.bat
)

if exist "frontend\node_modules" (
    echo [OK] Frontend dependencies installed
) else (
    echo [MISSING] Frontend dependencies not installed
    echo         Run: INSTALL.bat
)

if exist "backend\venv" (
    echo [OK] Python venv created
) else (
    echo [MISSING] Python venv not created
    echo         Run: INSTALL.bat
)

echo.
echo ========================================
echo.
pause
