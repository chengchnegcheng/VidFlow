@echo off
chcp 65001 >nul
title VidFlow Desktop - 清理缓存
color 0E

cd /d "%~dp0\.."

echo.
echo ========================================
echo   VidFlow Desktop - 清理缓存
echo ========================================
echo.
echo 这将清理以下内容：
echo   - 前端构建缓存 (frontend/dist)
echo   - 前端 node_modules/.vite
echo   - Electron 用户数据缓存
echo.

set /p confirm=确认清理？(Y/N):

if /i not "%confirm%"=="Y" (
    echo 已取消
    pause
    exit /b 0
)

echo.
echo 正在清理...
echo.

REM 清理前端构建
if exist "frontend\dist" (
    echo [1/3] 清理前端构建目录...
    rmdir /s /q "frontend\dist"
    echo ✅ 完成
) else (
    echo [1/3] 前端构建目录不存在，跳过
)

REM 清理 Vite 缓存
if exist "frontend\node_modules\.vite" (
    echo [2/3] 清理 Vite 缓存...
    rmdir /s /q "frontend\node_modules\.vite"
    echo ✅ 完成
) else (
    echo [2/3] Vite 缓存不存在，跳过
)

REM 清理 Electron 缓存
if exist "%APPDATA%\vidflow-desktop" (
    echo [3/3] 清理 Electron 用户数据...
    rmdir /s /q "%APPDATA%\vidflow-desktop"
    echo ✅ 完成
) else (
    echo [3/3] Electron 用户数据不存在，跳过
)

echo.
echo ========================================
echo   ✅ 清理完成！
echo ========================================
echo.
echo 现在可以重新启动应用：
echo   npm run dev
echo.
pause
