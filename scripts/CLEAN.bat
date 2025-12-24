@echo off
title VidFlow Desktop - Clean Project

REM Switch to project root directory
cd /d "%~dp0.."

echo ========================================
echo   VidFlow Desktop - Clean Project
echo ========================================
echo.
echo This will delete:
echo   - node_modules folders
echo   - Python virtual environment
echo   - Build artifacts
echo   - Cache files
echo.
echo WARNING: You will need to run INSTALL.bat again!
echo.
pause

echo.
echo [1/5] Cleaning root node_modules...
if exist "node_modules" (
    rmdir /s /q node_modules
    echo [OK] Deleted root node_modules
) else (
    echo [INFO] Root node_modules not found
)

echo.
echo [2/5] Cleaning frontend node_modules...
if exist "frontend\node_modules" (
    rmdir /s /q frontend\node_modules
    echo [OK] Deleted frontend node_modules
) else (
    echo [INFO] Frontend node_modules not found
)

echo.
echo [3/5] Cleaning Python virtual environment...
if exist "backend\venv" (
    rmdir /s /q backend\venv
    echo [OK] Deleted Python venv
) else (
    echo [INFO] Python venv not found
)

echo.
echo [4/5] Cleaning build artifacts...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "frontend\dist" rmdir /s /q frontend\dist
echo [OK] Build artifacts cleaned

echo.
echo [5/5] Cleaning cache files...
if exist "backend\__pycache__" rmdir /s /q backend\__pycache__
if exist "backend\data" rmdir /s /q backend\data
if exist ".vite" rmdir /s /q .vite
echo [OK] Cache files cleaned

echo.
echo ========================================
echo   Clean Complete!
echo ========================================
echo.
echo Run INSTALL.bat to reinstall dependencies
echo.
pause
