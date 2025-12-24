@echo off
chcp 65001 >nul
echo ========================================
echo VidFlow Desktop - 图标缓存清理工具
echo ========================================
echo.

echo [1/3] 正在关闭 VidFlow Desktop...
taskkill /IM "VidFlow Desktop.exe" /F 2>nul
taskkill /IM electron.exe /F 2>nul
timeout /t 2 /nobreak >nul
echo ✓ 应用已关闭
echo.

echo [2/3] 正在清除 Windows 图标缓存...
taskkill /IM explorer.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul

del /f /s /q /a "%userprofile%\AppData\Local\IconCache.db" 2>nul
del /f /s /q /a "%localappdata%\Microsoft\Windows\Explorer\iconcache*.db" 2>nul

start explorer.exe
timeout /t 2 /nobreak >nul
echo ✓ 图标缓存已清除
echo.

echo [3/3] 正在重新启动 VidFlow Desktop...
cd /d "%~dp0"
start cmd /c "npm run dev"
timeout /t 3 /nobreak >nul
echo ✓ 应用正在启动
echo.

echo ========================================
echo 完成！新图标应该在几秒钟后显示
echo ========================================
echo.
echo 如果图标仍未更新，请尝试：
echo 1. 重启电脑
echo 2. 或等待 1-2 分钟让 Windows 刷新缓存
echo.
pause
