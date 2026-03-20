#!/bin/bash
################################################################################
# VidFlow macOS 一键构建脚本
# 自动化构建 macOS DMG 安装包
################################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 获取脚本所在目录的上级目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." &> /dev/null && pwd )"

cd "$PROJECT_ROOT"

log_header "VidFlow macOS 构建脚本"
log_info "项目路径: $PROJECT_ROOT"
log_info "构建平台: macOS ($(uname -m))"
log_info "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ============================================================================
# 步骤 1: 环境检查
# ============================================================================
log_header "步骤 1/6: 环境检查"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    log_error "Node.js 未安装"
    log_info "请运行: brew install node"
    exit 1
fi
log_success "Node.js: $(node --version)"

# 检查 npm
if ! command -v npm &> /dev/null; then
    log_error "npm 未安装"
    exit 1
fi
log_success "npm: $(npm --version)"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 未安装"
    log_info "请运行: brew install python@3.11"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | awk '{print $2}')

# 检查 Python 版本是否为 beta/rc
if [[ "$PYTHON_VERSION" =~ (a|b|rc) ]]; then
    log_error "检测到 Python Beta/RC 版本: Python $PYTHON_VERSION"
    log_error "SQLAlchemy 不支持 Python 测试版本"
    log_info "请运行以下命令安装稳定版并重新构建:"
    echo "  brew install python@3.11"
    echo "  cd backend && rm -rf venv"
    echo "  /opt/homebrew/bin/python3.11 -m venv venv"
    echo "  source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

log_success "Python: $PYTHON_VERSION"

# 检查 Python 版本（推荐 3.11）
PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 12 ]; then
    log_warning "Python $PYTHON_VERSION 可能不兼容 AI 工具（faster-whisper 需要 3.11）"
    log_warning "推荐使用 Python 3.11: brew install python@3.11"
fi

# 检查 iconutil（生成 .icns 图标）
if ! command -v iconutil &> /dev/null; then
    log_warning "iconutil 未找到（macOS 自带工具）"
fi

echo ""

# ============================================================================
# 步骤 1.5: 下载 macOS 版本的工具（ffmpeg, ffprobe, yt-dlp）
# ============================================================================
log_header "步骤 1.5/6: 下载 macOS 工具"

TOOLS_BIN_DIR="$PROJECT_ROOT/resources/tools/bin"
mkdir -p "$TOOLS_BIN_DIR"

# 下载 ffmpeg (macOS)
# 注意: evermeet.cx 提供的是 Intel (x86_64) 版本
# Apple Silicon Mac 会通过 Rosetta 2 运行，或者用户可以使用 Homebrew 安装原生版本
if [ ! -f "$TOOLS_BIN_DIR/ffmpeg" ]; then
    log_info "下载 ffmpeg (macOS x86_64)..."
    FFMPEG_URL="https://evermeet.cx/ffmpeg/ffmpeg-7.1.zip"
    FFMPEG_ZIP="$TOOLS_BIN_DIR/ffmpeg.zip"

    if curl -L -o "$FFMPEG_ZIP" "$FFMPEG_URL"; then
        unzip -o "$FFMPEG_ZIP" -d "$TOOLS_BIN_DIR"
        rm -f "$FFMPEG_ZIP"
        chmod +x "$TOOLS_BIN_DIR/ffmpeg"
        log_success "ffmpeg 下载完成"

        # 检查架构
        if [ "$(uname -m)" = "arm64" ]; then
            log_warning "注意: 下载的 ffmpeg 是 Intel 版本，将通过 Rosetta 2 运行"
            log_info "如需原生 ARM64 版本，可运行: brew install ffmpeg"
        fi
    else
        log_warning "ffmpeg 下载失败，将在运行时自动下载"
    fi
else
    log_success "ffmpeg 已存在"
fi

# 下载 ffprobe (macOS)
if [ ! -f "$TOOLS_BIN_DIR/ffprobe" ]; then
    log_info "下载 ffprobe (macOS)..."
    FFPROBE_URL="https://evermeet.cx/ffmpeg/ffprobe-7.1.zip"
    FFPROBE_ZIP="$TOOLS_BIN_DIR/ffprobe.zip"

    if curl -L -o "$FFPROBE_ZIP" "$FFPROBE_URL"; then
        unzip -o "$FFPROBE_ZIP" -d "$TOOLS_BIN_DIR"
        rm -f "$FFPROBE_ZIP"
        chmod +x "$TOOLS_BIN_DIR/ffprobe"
        log_success "ffprobe 下载完成"
    else
        log_warning "ffprobe 下载失败，将在运行时自动下载"
    fi
else
    log_success "ffprobe 已存在"
fi

# 下载 yt-dlp (macOS)
# yt-dlp_macos 是 Universal Binary，支持 Intel 和 Apple Silicon
if [ ! -f "$TOOLS_BIN_DIR/yt-dlp" ]; then
    log_info "下载 yt-dlp (macOS Universal Binary)..."
    YTDLP_URL="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"

    if curl -L -o "$TOOLS_BIN_DIR/yt-dlp" "$YTDLP_URL"; then
        chmod +x "$TOOLS_BIN_DIR/yt-dlp"
        # 验证下载的文件
        if file "$TOOLS_BIN_DIR/yt-dlp" | grep -q "Mach-O"; then
            log_success "yt-dlp 下载完成 ($(file "$TOOLS_BIN_DIR/yt-dlp" | grep -o 'universal\|x86_64\|arm64' | head -1))"
        else
            log_success "yt-dlp 下载完成"
        fi
    else
        log_warning "yt-dlp 下载失败，将在运行时自动下载"
    fi
else
    log_success "yt-dlp 已存在"
fi

# 验证工具
log_info "验证工具..."
if [ -f "$TOOLS_BIN_DIR/ffmpeg" ] && [ -f "$TOOLS_BIN_DIR/ffprobe" ] && [ -f "$TOOLS_BIN_DIR/yt-dlp" ]; then
    log_success "所有 macOS 工具已就绪"
    ls -la "$TOOLS_BIN_DIR"
else
    log_warning "部分工具缺失，应用将在首次运行时自动下载"
fi

echo ""

# ============================================================================
# 步骤 2: 安装依赖
# ============================================================================
log_header "步骤 2/6: 安装依赖"

log_info "安装根目录 npm 依赖..."
npm install
log_success "根目录依赖安装完成"

log_info "安装前端依赖..."
cd frontend
npm install
cd ..
log_success "前端依赖安装完成"

log_info "设置 Python 虚拟环境..."
cd backend

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    log_info "创建 Python 虚拟环境..."
    python3 -m venv venv
    log_success "虚拟环境创建完成"
else
    log_success "虚拟环境已存在"
fi

# 激活虚拟环境并安装依赖
log_info "安装 Python 依赖..."
source venv/bin/activate

# 升级 pip
pip install --upgrade pip > /dev/null 2>&1

# 安装依赖
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    log_success "Python 依赖安装完成"
else
    log_warning "requirements.txt 未找到"
fi

deactivate
cd ..

echo ""

# ============================================================================
# 步骤 3: 生成 macOS 图标
# ============================================================================
log_header "步骤 3/7: 生成图标"

if [ ! -f "resources/icon.icns" ]; then
    log_info "生成 macOS .icns 图标..."
    node scripts/generate-icns.js

    if [ -f "resources/icon.icns" ]; then
        log_success "图标生成成功"
    else
        log_warning "图标生成失败，将使用默认图标"
    fi
else
    log_success "图标已存在: resources/icon.icns"
fi

echo ""

# ============================================================================
# 步骤 4: 构建前端
# ============================================================================
log_header "步骤 4/7: 构建前端"

log_info "正在构建前端资源..."
cd frontend
npm run build

if [ -d "dist" ]; then
    log_success "前端构建完成"
    log_info "输出目录: frontend/dist"
else
    log_error "前端构建失败"
    exit 1
fi
cd ..

echo ""

# ============================================================================
# 步骤 5: 构建后端
# ============================================================================
log_header "步骤 5/7: 构建后端"

log_info "正在打包 Python 后端..."
cd backend

# 激活虚拟环境
source venv/bin/activate

# 使用 PyInstaller 打包
if ! command -v pyinstaller &> /dev/null; then
    log_info "安装 PyInstaller..."
    pip install pyinstaller
fi

# 清理旧的构建文件
if [ -d "dist" ]; then
    log_info "清理旧的构建文件..."
    rm -rf dist
fi

if [ -d "build" ]; then
    rm -rf build
fi

# 执行打包
log_info "执行 PyInstaller 打包（这可能需要几分钟）..."
python -m PyInstaller backend.spec --clean --noconfirm

if [ -f "dist/VidFlow-Backend/VidFlow-Backend" ]; then
    # 设置可执行权限
    chmod +x dist/VidFlow-Backend/VidFlow-Backend
    log_success "后端打包完成"
    log_info "输出目录: backend/dist/VidFlow-Backend"

    # 显示文件大小
    BACKEND_SIZE=$(du -sh dist/VidFlow-Backend | awk '{print $1}')
    log_info "后端大小: $BACKEND_SIZE"
else
    log_error "后端打包失败"
    deactivate
    exit 1
fi

deactivate
cd ..

echo ""

# ============================================================================
# 步骤 6: 打包 Electron 应用
# ============================================================================
log_header "步骤 6/7: 打包 macOS 应用"

log_info "正在打包 Electron 应用..."

# 检查架构
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    log_info "检测到 Apple Silicon (M1/M2/M3)"
    log_info "将构建通用二进制（x64 + arm64）"
else
    log_info "检测到 Intel Mac"
    log_info "将构建 x64 版本"
fi

# 执行打包
npm run build:mac

# 检查输出
if [ -d "dist-output" ]; then
    log_success "打包完成！"
    echo ""
    log_info "输出目录: dist-output/"

    # 列出生成的文件
    echo ""
    log_header "生成的文件"
    for file in dist-output/*.dmg dist-output/*.zip dist-output/mac*/*.app; do
        if [ -e "$file" ]; then
            SIZE=$(du -sh "$file" | awk '{print $1}')
            echo "  📦 $(basename "$file") ($SIZE)"
        fi
    done

    echo ""
    log_success "🎉 构建完成！"
    echo ""
    log_info "安装说明:"
    echo "  1. 打开 dist-output/ 目录"
    echo "  2. 双击 .dmg 文件"
    echo "  3. 将 VidFlow 拖到 Applications 文件夹"
    echo ""

    # 检查代码签名状态
    DMG_FILE=$(find dist-output -name "*.dmg" -type f | head -n 1)
    if [ -n "$DMG_FILE" ]; then
        log_info "提示: 应用未签名，首次运行时请:"
        echo "  - 右键点击应用"
        echo "  - 选择 '打开'"
        echo "  - 在弹出的对话框中确认"
    fi

else
    log_error "打包失败"
    log_info "请检查上述错误信息"
    exit 1
fi

echo ""
log_header "构建完成"
echo ""
