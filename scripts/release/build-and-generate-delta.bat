@echo off
chcp 936 >nul
setlocal

cd /d "%~dp0\..\.."
title VidFlow - 构建并生成增量包
color 0E

node scripts\release\build-and-generate-delta.js %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [错误] 构建并生成增量包失败。
) else (
    echo [完成] 构建并生成增量包完成。
)
echo.
call :pause_if_needed
exit /b %EXIT_CODE%

:pause_if_needed
if /i not "%VIDFLOW_SKIP_PAUSE%"=="1" pause
exit /b 0