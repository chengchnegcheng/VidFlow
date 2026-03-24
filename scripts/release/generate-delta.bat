@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0\.."
title VidFlow - Generate Delta Update Package
color 0E

node scripts\generate-delta.js %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Delta package generation failed.
) else (
    echo [OK] Delta package generation finished.
)
echo.
pause
exit /b %EXIT_CODE%
