@echo off
echo ========================================
echo Windows Icon Cache Cleaner
echo ========================================
echo.
echo This script will clear Windows icon cache to refresh application icons.
echo Please close all running applications before proceeding.
echo.
pause

echo.
echo [1/3] Stopping Windows Explorer...
taskkill /f /im explorer.exe

echo.
echo [2/3] Deleting icon cache files...
cd /d "%LOCALAPPDATA%"
if exist IconCache.db (
    del /f /q IconCache.db
    echo   - Deleted IconCache.db
)
if exist Microsoft\Windows\Explorer\iconcache*.db (
    del /f /q Microsoft\Windows\Explorer\iconcache*.db
    echo   - Deleted iconcache files
)

echo.
echo [3/3] Restarting Windows Explorer...
start explorer.exe

echo.
echo ========================================
echo Icon cache cleared successfully!
echo ========================================
echo.
echo Please restart VidFlow to see the new icon.
echo.
pause
