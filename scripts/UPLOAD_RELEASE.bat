@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0\.."
title VidFlow - Upload Release
color 0A

for /f "delims=" %%v in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Host $json.version -NoNewline"') do set "VERSION=%%v"

echo.
echo ========================================
echo   VidFlow - Release Upload Script
echo ========================================
echo.
echo [INFO] Current version: %VERSION%
echo.

set "INSTALLER_PATH=dist-output\VidFlow-Setup-%VERSION%.exe"
if not exist "%INSTALLER_PATH%" (
    set "INSTALLER_PATH=dist-output\VidFlow Setup %VERSION%.exe"
)

if not exist "%INSTALLER_PATH%" (
    echo [ERROR] Installer not found.
    echo [INFO] Build the release first with BUILD_RELEASE.bat or npm run build.
    echo.
    dir dist-output\*.exe 2>nul
    pause
    exit /b 1
)

echo [INFO] Installer: %INSTALLER_PATH%
for %%f in ("%INSTALLER_PATH%") do set "INSTALLER_FILE_NAME=%%~nxf"
echo.
echo [INFO] Calculating installer hash...
for /f "delims=" %%h in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -Path '%INSTALLER_PATH%' -Algorithm SHA512).Hash.ToLower()"') do set "FILE_HASH=%%h"
for /f "delims=" %%s in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Item '%INSTALLER_PATH%').Length"') do set "FILE_SIZE=%%s"

echo [INFO] SHA-512: %FILE_HASH:~0,32%...
echo [INFO] Size: %FILE_SIZE% bytes
echo.
echo ========================================
echo Upload Options
echo ========================================
echo.
echo [1] Upload to update server (manual)
echo [2] Generate release metadata JSON
echo [3] Sync to local releases directory
echo [0] Exit
echo.

set /p choice=Select an option:

if "%choice%"=="1" goto upload_server
if "%choice%"=="2" goto generate_json
if "%choice%"=="3" goto copy_local
goto end

:upload_server
echo.
echo [INFO] Upload to update server
echo.
echo [INFO] Configure your server credentials, then upload the installer manually.
echo [INFO] Example:
echo   scp "%INSTALLER_PATH%" user@shcrystal.top:/path/to/releases/v%VERSION%/
echo.
pause
goto end

:generate_json
echo.
echo [INFO] Generating release metadata...
set "JSON_FILE=dist-output\release-%VERSION%.json"

(
echo {
echo   "version": "%VERSION%",
echo   "platform": "win32",
echo   "arch": "x64",
echo   "file_name": "%INSTALLER_FILE_NAME%",
echo   "file_size": %FILE_SIZE%,
echo   "file_hash": "%FILE_HASH%",
echo   "download_url": "https://shcrystal.top:8321/releases/v%VERSION%/%INSTALLER_FILE_NAME%",
echo   "release_notes": "",
echo   "is_mandatory": false,
echo   "channel": "stable"
echo }
) > "%JSON_FILE%"

echo.
echo [OK] Metadata generated: %JSON_FILE%
echo.
type "%JSON_FILE%"
echo.
pause
goto end

:copy_local
echo.
echo [INFO] Syncing current build outputs into releases\v%VERSION% ...
echo [INFO] Existing snapshot will be replaced to avoid stale files affecting delta generation.
node scripts\archive-release.js --version=%VERSION%
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to sync local release snapshot.
    pause
    goto end
)
echo.
echo [INFO] You can now run GENERATE_DELTA.bat or npm run delta -- sourceVersion
echo.
pause
goto end

:end
echo.
echo Exit.
exit /b 0
