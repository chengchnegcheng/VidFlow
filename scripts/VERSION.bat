@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0\.."
title VidFlow - 版本号管理
color 0B

:menu
cls
echo.
echo ========================================
echo   VidFlow - 版本号管理
echo ========================================
echo.

REM 使用 PowerShell 读取版本号
set "CURRENT_VERSION="
for /f "delims=" %%v in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Host $json.version -NoNewline"') do set "CURRENT_VERSION=%%v"

if not defined CURRENT_VERSION (
    echo ❌ 无法读取版本号
    pause
    exit /b 1
)

echo 📦 当前版本: %CURRENT_VERSION%
echo.
echo ========================================
echo.
echo 请选择操作：
echo.
echo [1] 修改版本号
echo [2] 快速升级版本
echo     - 主版本 ^(1.0.0 → 2.0.0^)
echo     - 次版本 ^(1.0.0 → 1.1.0^)
echo     - 修订版 ^(1.0.0 → 1.0.1^)
echo [3] 查看详细信息
echo [4] 生成更新日志模板
echo [0] 退出
echo.

set /p choice=请输入选项 [0-4]:

if "%choice%"=="1" goto custom_version
if "%choice%"=="2" goto quick_upgrade
if "%choice%"=="3" goto show_details
if "%choice%"=="4" goto changelog
if "%choice%"=="0" goto end
goto menu

:custom_version
cls
echo.
echo ========================================
echo   自定义版本号
echo ========================================
echo.
echo 当前版本: %CURRENT_VERSION%
echo.
set /p NEW_VERSION=请输入新版本号 (例如 1.1.0):

if not defined NEW_VERSION (
    echo ❌ 版本号不能为空
    pause
    goto menu
)

goto confirm_change

:quick_upgrade
cls
echo.
echo ========================================
echo   快速升级版本
echo ========================================
echo.
echo 当前版本: %CURRENT_VERSION%
echo.
echo [1] 主版本升级 ^(重大更新^)
echo [2] 次版本升级 ^(新功能^)
echo [3] 修订版升级 ^(修复bug^)
echo [0] 返回
echo.
set /p upgrade_type=请选择 [0-3]:

if "%upgrade_type%"=="0" goto menu

REM 使用 PowerShell 计算新版本
for /f "delims=" %%v in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$v = '%CURRENT_VERSION%'.Split('.'); $major = [int]$v[0]; $minor = [int]$v[1]; $patch = [int]$v[2]; if ('%upgrade_type%' -eq '1') { $major++; $minor=0; $patch=0 } elseif ('%upgrade_type%' -eq '2') { $minor++; $patch=0 } elseif ('%upgrade_type%' -eq '3') { $patch++ } else { exit 1 }; Write-Host \"$major.$minor.$patch\" -NoNewline"') do set "NEW_VERSION=%%v"

if not defined NEW_VERSION (
    echo ❌ 无效选项
    pause
    goto menu
)

if "%upgrade_type%"=="1" echo 🚀 主版本升级
if "%upgrade_type%"=="2" echo ✨ 次版本升级
if "%upgrade_type%"=="3" echo 🐛 修订版升级

goto confirm_change

:confirm_change
echo.
echo ========================================
echo   确认修改
echo ========================================
echo.
echo 当前版本: %CURRENT_VERSION%
echo 新版本:   %NEW_VERSION%
echo.
echo 将修改以下文件：
echo   - package.json
echo   - frontend\package.json
echo   - backend\src\main.py
echo   - frontend\src\App.tsx
echo.
echo 注意: electron-builder 会自动从 package.json 读取版本号
echo.
set /p confirm=确认修改？^(Y/N^):

if /i not "%confirm%"=="Y" (
    echo ❌ 已取消
    pause
    goto menu
)

echo.
echo 正在修改版本号...
echo.

REM 1. 修改根目录 package.json
echo [1/5] package.json
powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content 'package.json' -Raw -Encoding UTF8 | ConvertFrom-Json; $json.version = '%NEW_VERSION%'; $jsonText = ($json | ConvertTo-Json -Depth 100) -replace '\":\s+', '\": '; [System.IO.File]::WriteAllText((Resolve-Path 'package.json').Path, $jsonText, (New-Object System.Text.UTF8Encoding $false))"
if errorlevel 1 (
    echo ❌ 失败
    pause
    goto menu
)
echo ✅ 完成

REM 2. 修改 frontend/package.json
echo [2/5] frontend\package.json
if exist "frontend\package.json" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$json = Get-Content 'frontend\package.json' -Raw -Encoding UTF8 | ConvertFrom-Json; $json.version = '%NEW_VERSION%'; $jsonText = ($json | ConvertTo-Json -Depth 100) -replace '\":\s+', '\": '; [System.IO.File]::WriteAllText((Resolve-Path 'frontend\package.json').Path, $jsonText, (New-Object System.Text.UTF8Encoding $false))"
    if errorlevel 1 (
        echo ❌ 失败
        pause
        goto menu
    )
    echo ✅ 完成
) else (
    echo ⚠️ 文件不存在
)

REM 3. 修改 backend/src/main.py
echo [3/4] backend\src\main.py
if exist "backend\src\main.py" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$path = 'backend\src\main.py'; $content = Get-Content $path -Raw -Encoding UTF8; $content = $content -replace 'version=\"[0-9.]+\"', 'version=\"%NEW_VERSION%\"'; [System.IO.File]::WriteAllText((Resolve-Path $path), $content, (New-Object System.Text.UTF8Encoding $false))"
    if errorlevel 1 (
        echo ❌ 失败
        pause
        goto menu
    )
    echo ✅ 完成
) else (
    echo ⚠️ 文件不存在
)

REM 4. 修改 frontend/src/App.tsx
echo [4/4] frontend\src\App.tsx
if exist "frontend\src\App.tsx" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$path = 'frontend\src\App.tsx'; $content = Get-Content $path -Raw -Encoding UTF8; $content = $content -replace 'useState<string>\(''[0-9.]+''\)', 'useState<string>(''%NEW_VERSION%'')'; [System.IO.File]::WriteAllText((Resolve-Path $path), $content, (New-Object System.Text.UTF8Encoding $false))"
    if errorlevel 1 (
        echo ❌ 失败
        pause
        goto menu
    )
    echo ✅ 完成
) else (
    echo ⚠️ 文件不存在
)

echo.
echo ========================================
echo   ✅ 版本号修改成功！
echo ========================================
echo.
echo %CURRENT_VERSION% → %NEW_VERSION%
echo.
pause
goto menu

:show_details
cls
echo.
echo ========================================
echo   版本详细信息
echo ========================================
echo.
echo 📦 package.json
findstr /C:"\"version\"" package.json
echo.
echo 📦 frontend\package.json
if exist "frontend\package.json" findstr /C:"\"version\"" frontend\package.json
echo.
echo 📦 backend\src\main.py
if exist "backend\src\main.py" findstr /C:"version=" backend\src\main.py | findstr /C:"FastAPI"
echo.
echo 📦 frontend\src\App.tsx
if exist "frontend\src\App.tsx" findstr /C:"useState<string>" frontend\src\App.tsx | findstr /C:"appVersion"
echo.
echo ========================================
pause
goto menu

:changelog
cls
echo.
echo ========================================
echo   生成更新日志模板
echo ========================================
echo.

set "CHANGELOG_FILE=CHANGELOG_%CURRENT_VERSION%.md"

(
echo # VidFlow Desktop v%CURRENT_VERSION%
echo.
echo **发布日期**: %date%
echo.
echo ---
echo.
echo ## 🎉 新功能
echo - ✨ 添加了 XXX 功能
echo.
echo ## 🎨 优化改进
echo - ⚡ 优化了性能
echo.
echo ## 🐛 问题修复
echo - 🐛 修复了已知问题
echo.
echo ---
) > "%CHANGELOG_FILE%"

echo ✅ 已生成: %CHANGELOG_FILE%
echo.
pause

if exist "%CHANGELOG_FILE%" start notepad "%CHANGELOG_FILE%"
goto menu

:end
cls
echo 退出
exit /b 0
