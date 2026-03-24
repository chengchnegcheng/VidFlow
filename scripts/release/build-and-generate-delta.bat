@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0\.."
title VidFlow - Build And Generate Delta
color 0E

node scripts\build-and-generate-delta.js %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Build and delta generation failed.
) else (
    echo [OK] Build and delta generation finished.
)
echo.
pause
exit /b %EXIT_CODE%
