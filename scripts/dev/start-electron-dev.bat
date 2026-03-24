@echo off
setlocal
chcp 65001 >nul
title VidFlow Electron Dev

cd /d "%~dp0\.."
set "DISABLE_BACKEND_AUTO_START=1"
set "VIDFLOW_REUSE_EXISTING_BACKEND=1"

echo [Electron] Reusing backend from START.bat
echo [Electron] DISABLE_BACKEND_AUTO_START=%DISABLE_BACKEND_AUTO_START%
echo [Electron] VIDFLOW_REUSE_EXISTING_BACKEND=%VIDFLOW_REUSE_EXISTING_BACKEND%

call npm run electron:dev
