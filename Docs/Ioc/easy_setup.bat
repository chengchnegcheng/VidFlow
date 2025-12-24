@echo off
chcp 65001 >nul
echo.
echo 🎨 VidFlow Desktop 图标生成器 - 简易安装
echo ================================================
echo.

REM 检查是否存在 SVG 文件
if not exist "icon.svg" (
    echo ❌ 未找到 icon.svg 文件
    pause
    exit /b 1
)

echo ✓ 找到 icon.svg 文件
echo.

REM 检查是否已安装 Inkscape
where inkscape >nul 2>nul
if %errorlevel% == 0 (
    echo ✓ 找到 Inkscape，开始生成图标...
    goto :generate_icons
)

echo ❌ 未找到 Inkscape
echo.
echo 📦 安装选项:
echo [1] 自动下载并安装 Inkscape (推荐)
echo [2] 手动安装 Inkscape
echo [3] 使用在线转换工具
echo [4] 退出
echo.
set /p choice="请选择 (1-4): "

if "%choice%"=="1" goto :auto_install
if "%choice%"=="2" goto :manual_install
if "%choice%"=="3" goto :online_convert
if "%choice%"=="4" goto :end

:auto_install
echo.
echo 🔄 正在下载 Inkscape...
echo 这可能需要几分钟时间，请耐心等待...
echo.

REM 检查是否有 winget
where winget >nul 2>nul
if %errorlevel% == 0 (
    echo 使用 winget 安装 Inkscape...
    winget install --id=Inkscape.Inkscape -e
    if %errorlevel% == 0 (
        echo ✓ Inkscape 安装成功
        echo 请重新运行此脚本生成图标
        pause
        exit /b 0
    )
)

REM 检查是否有 chocolatey
where choco >nul 2>nul
if %errorlevel% == 0 (
    echo 使用 Chocolatey 安装 Inkscape...
    choco install inkscape -y
    if %errorlevel% == 0 (
        echo ✓ Inkscape 安装成功
        echo 请重新运行此脚本生成图标
        pause
        exit /b 0
    )
)

echo ❌ 自动安装失败
echo 请手动安装 Inkscape 或选择其他方案
goto :manual_install

:manual_install
echo.
echo 📋 手动安装步骤:
echo 1. 访问: https://inkscape.org/release/
echo 2. 下载 Windows 版本
echo 3. 安装完成后重新运行此脚本
echo.
echo 按任意键打开下载页面...
pause >nul
start https://inkscape.org/release/
goto :end

:online_convert
echo.
echo 🌐 在线转换方案:
echo.
echo 1. 打开在线转换工具:
echo    - https://convertio.co/svg-png/
echo    - https://cloudconvert.com/svg-to-png/
echo.
echo 2. 上传 icon.svg 文件
echo.
echo 3. 转换以下尺寸:
echo    16×16, 24×24, 32×32, 48×48, 64×64
echo    96×96, 128×128, 256×256, 512×512, 1024×1024
echo.
echo 4. 下载并重命名为:
echo    vidflow-16x16.png, vidflow-24x24.png 等
echo.
echo 5. 放入 icons\png\ 目录
echo.
echo 按任意键打开转换网站...
pause >nul
start https://convertio.co/svg-png/
goto :end

:generate_icons
echo.
echo 📦 创建输出目录...
if not exist "icons" mkdir icons
if not exist "icons\png" mkdir icons\png
if not exist "icons\ico" mkdir icons\ico

echo.
echo 🎨 生成 PNG 图标...

REM 生成各种尺寸的 PNG
set sizes=16 24 32 48 64 96 128 256 512 1024

for %%s in (%sizes%) do (
    echo 生成 %%s×%%s...
    inkscape --export-type=png --export-filename=icons\png\vidflow-%%sx%%s.png --export-width=%%s --export-height=%%s icon.svg >nul 2>&1
    if exist "icons\png\vidflow-%%sx%%s.png" (
        echo ✓ vidflow-%%sx%%s.png
    ) else (
        echo ❌ vidflow-%%sx%%s.png 生成失败
    )
)

echo.
echo 🔧 生成 ICO 文件...

REM 检查是否有 ImageMagick
where magick >nul 2>nul
if %errorlevel% == 0 (
    magick icons\png\vidflow-16x16.png icons\png\vidflow-24x24.png icons\png\vidflow-32x32.png icons\png\vidflow-48x48.png icons\png\vidflow-64x64.png icons\png\vidflow-128x128.png icons\png\vidflow-256x256.png icons\ico\vidflow.ico >nul 2>&1
    if exist "icons\ico\vidflow.ico" (
        echo ✓ vidflow.ico
    ) else (
        echo ❌ ICO 生成失败
    )
) else (
    echo ⚠️  未找到 ImageMagick，跳过 ICO 生成
    echo 💡 可选安装: https://imagemagick.org/
)

echo.
echo ✅ 图标生成完成!
echo 📁 查看 icons\ 目录获取所有图标文件
echo 🌐 打开 icon_preview.html 预览效果
echo.

REM 询问是否打开预览
set /p open_preview="是否打开预览页面? (y/n): "
if /i "%open_preview%"=="y" (
    start icon_preview.html
)

:end
echo.
pause