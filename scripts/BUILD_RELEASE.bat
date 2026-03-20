@echo off
chcp 65001 >nul
echo ===============================================
echo VidFlow 发布构建脚本
echo ===============================================
echo.

:menu
echo 请选择构建类型：
echo.
echo [1] 完整构建（后端 + 前端 + 打包）
echo [2] 仅构建后端
echo [3] 仅构建前端
echo [4] 仅打包 Electron
echo [5] 快速打包（不重新构建后端/前端）
echo [6] 查看构建产物
echo [7] 清理构建缓存
echo [0] 退出
echo.

set /p choice=请输入选项 [0-7]:

if "%choice%"=="1" goto build_all
if "%choice%"=="2" goto build_backend
if "%choice%"=="3" goto build_frontend
if "%choice%"=="4" goto build_electron
if "%choice%"=="5" goto package_only
if "%choice%"=="6" goto show_output
if "%choice%"=="7" goto clean
if "%choice%"=="0" goto end
goto menu

:build_all
echo.
echo ========================================
echo 开始完整构建流程...
echo ========================================
echo.

echo [1/4] 检查版本号...
powershell -Command "Get-Content package.json | Select-String -Pattern '\"version\"' | Select-Object -First 1"
echo.
set /p confirm=确认版本号正确吗？(Y/N):
if /i not "%confirm%"=="Y" goto menu

echo.
echo [2/4] 构建后端 (PyInstaller)...
cd backend

REM 检查虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo ❌ 虚拟环境不存在！
    echo 💡 请先运行 SETUP.bat 创建虚拟环境
    cd ..
    pause
    goto menu
)

echo [INFO] 使用虚拟环境中的 Python...
venv\Scripts\python.exe --version
echo.

REM 使用虚拟环境中的 Python 运行 PyInstaller
venv\Scripts\python.exe -m PyInstaller backend.spec --clean --noconfirm
if errorlevel 1 (
    echo ❌ 后端构建失败！
    cd ..
    pause
    goto menu
)
cd ..
echo ✅ 后端构建完成

echo.
echo [3/4] 构建前端 (Vite)...
cd frontend
call npm run build
if errorlevel 1 (
    echo ❌ 前端构建失败！
    cd ..
    pause
    goto menu
)
cd ..
echo ✅ 前端构建完成

echo.
echo [4/4] 打包 Electron (electron-builder)...
call npm run build:electron
if errorlevel 1 (
    echo ❌ Electron 打包失败！
    pause
    goto menu
)
echo ✅ Electron 打包完成

echo.
echo ========================================
echo 🎉 完整构建流程完成！
echo ========================================
echo.
echo 构建产物位于 dist-output 目录
echo.
pause
goto show_output

:build_backend
echo.
echo 构建后端...
cd backend

REM 检查虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo ❌ 虚拟环境不存在！
    echo 💡 请先运行 SETUP.bat 创建虚拟环境
    cd ..
    pause
    goto menu
)

REM 显示使用的 Python 版本
echo [INFO] 使用虚拟环境中的 Python...
venv\Scripts\python.exe --version

REM 使用虚拟环境中的 Python 运行 PyInstaller
echo [INFO] 使用 PyInstaller 打包后端...
venv\Scripts\python.exe -m PyInstaller backend.spec --clean --noconfirm

if errorlevel 1 (
    echo ❌ 后端构建失败！
) else (
    echo ✅ 后端构建完成
)
cd ..
echo.
pause
goto menu

:build_frontend
echo.
echo 构建前端...
cd frontend
call npm run build
if errorlevel 1 (
    echo ❌ 前端构建失败！
) else (
    echo ✅ 前端构建完成
)
cd ..
echo.
pause
goto menu

:build_electron
echo.
echo 打包 Electron...
call npm run build:electron
if errorlevel 1 (
    echo ❌ Electron 打包失败！
) else (
    echo ✅ Electron 打包完成
)
echo.
pause
goto menu

:package_only
echo.
echo 快速打包（使用现有构建）...
call npm run package:win
if errorlevel 1 (
    echo ❌ 打包失败！
) else (
    echo ✅ 打包完成
)
echo.
pause
goto menu

:show_output
echo.
echo ========================================
echo 构建产物列表
echo ========================================
if exist "dist-output" (
    dir /B "dist-output\*.exe"
    echo.
    echo 详细信息：
    dir "dist-output\*.exe"
) else (
    echo ❌ dist-output 目录不存在
)
echo.
pause
goto menu

:clean
echo.
echo 清理构建缓存...
echo.
if exist "backend\build" (
    rmdir /S /Q "backend\build"
    echo ✅ 清理 backend\build
)
if exist "backend\dist" (
    rmdir /S /Q "backend\dist"
    echo ✅ 清理 backend\dist
)
if exist "frontend\dist" (
    rmdir /S /Q "frontend\dist"
    echo ✅ 清理 frontend\dist
)
if exist "dist-output" (
    rmdir /S /Q "dist-output"
    echo ✅ 清理 dist-output
)
echo.
echo 清理完成
pause
goto menu

:end
echo.
echo 退出构建脚本
exit /b 0

