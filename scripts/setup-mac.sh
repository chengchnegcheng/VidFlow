#!/bin/bash
################################################################################
# VidFlow macOS 环境初始化脚本
# 一键安装所有依赖和配置开发环境
################################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
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
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}  $1${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 获取脚本所在目录的上级目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." &> /dev/null && pwd )"

cd "$PROJECT_ROOT"

log_header "VidFlow macOS 环境初始化"
log_info "项目路径: $PROJECT_ROOT"
log_info "架构: $(uname -m)"
echo ""

# ============================================================================
# 步骤 1: 检查系统环境
# ============================================================================
log_header "步骤 1/5: 检查系统环境"

# 检查 macOS 版本
MACOS_VERSION=$(sw_vers -productVersion)
log_info "macOS 版本: $MACOS_VERSION"

# 检查架构
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    log_success "检测到 Apple Silicon (M1/M2/M3)"
    IS_APPLE_SILICON=true
else
    log_success "检测到 Intel Mac"
    IS_APPLE_SILICON=false
fi

echo ""

# ============================================================================
# 步骤 2: 检查并安装必要工具
# ============================================================================
log_header "步骤 2/5: 检查开发工具"

# 检查 Homebrew
if ! command -v brew &> /dev/null; then
    log_warning "Homebrew 未安装"
    log_info "是否安装 Homebrew? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "正在安装 Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        log_success "Homebrew 安装完成"
    else
        log_error "Homebrew 是必需的，安装已取消"
        exit 1
    fi
else
    log_success "Homebrew: $(brew --version | head -n 1)"
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    log_warning "Node.js 未安装"
    log_info "正在安装 Node.js..."
    brew install node
    log_success "Node.js 安装完成"
else
    log_success "Node.js: $(node --version)"
fi

# 检查 Python 3.11
PYTHON_CMD=""

# 检测 Python beta/rc 版本的函数
check_python_stability() {
    local py_cmd=$1
    local version=$($py_cmd --version 2>&1 | awk '{print $2}')

    if [[ "$version" =~ (a|b|rc) ]]; then
        return 1  # 不稳定版本
    else
        return 0  # 稳定版本
    fi
}

if command -v python3.11 &> /dev/null; then
    if check_python_stability "python3.11"; then
        PYTHON_CMD="python3.11"
        log_success "Python 3.11: $(python3.11 --version)"
    else
        log_error "检测到 Python 3.11 Beta/RC 版本: $(python3.11 --version)"
        log_error "SQLAlchemy 不支持 Python 测试版本"
        log_info "正在通过 Homebrew 安装稳定版..."
        brew install python@3.11
        PYTHON_CMD="/opt/homebrew/bin/python3.11"
        log_success "Python 3.11 稳定版安装完成"
    fi
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

    if [ "$PYTHON_MINOR" -eq 11 ]; then
        if check_python_stability "python3"; then
            PYTHON_CMD="python3"
            log_success "Python 3.11: $PYTHON_VERSION"
        else
            log_error "检测到 Python 3.11 Beta/RC 版本: $PYTHON_VERSION"
            log_error "SQLAlchemy 不支持 Python 测试版本"
            log_info "正在通过 Homebrew 安装稳定版..."
            brew install python@3.11
            PYTHON_CMD="/opt/homebrew/bin/python3.11"
            log_success "Python 3.11 稳定版安装完成"
        fi
    elif [ "$PYTHON_MINOR" -eq 12 ] || [ "$PYTHON_MINOR" -eq 13 ]; then
        log_warning "Python 3 已安装，但版本是 $PYTHON_VERSION"
        log_warning "AI 功能需要 Python 3.11（faster-whisper 不支持 3.12+）"
        log_info "是否安装 Python 3.11? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            brew install python@3.11
            PYTHON_CMD="/opt/homebrew/bin/python3.11"
            log_success "Python 3.11 安装完成"
        else
            PYTHON_CMD="python3"
            log_warning "使用现有 Python 版本，AI 功能将不可用"
        fi
    else
        log_warning "Python 3 已安装，但版本是 $PYTHON_VERSION"
        log_warning "推荐使用 Python 3.11"
        log_info "是否安装 Python 3.11? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            brew install python@3.11
            PYTHON_CMD="/opt/homebrew/bin/python3.11"
            log_success "Python 3.11 安装完成"
        else
            PYTHON_CMD="python3"
            log_warning "使用现有 Python 版本"
        fi
    fi
else
    log_info "正在安装 Python 3.11..."
    brew install python@3.11
    PYTHON_CMD="/opt/homebrew/bin/python3.11"
    log_success "Python 3.11 安装完成"
fi

# 检查 Git
if ! command -v git &> /dev/null; then
    log_warning "Git 未安装"
    log_info "正在安装 Git..."
    brew install git
    log_success "Git 安装完成"
else
    log_success "Git: $(git --version)"
fi

echo ""

# ============================================================================
# 步骤 3: 安装项目依赖
# ============================================================================
log_header "步骤 3/5: 安装项目依赖"

# 安装根目录依赖
log_info "安装根目录 npm 依赖..."
npm install
log_success "根目录依赖安装完成"

# 安装前端依赖
log_info "安装前端依赖..."
cd frontend
npm install
cd ..
log_success "前端依赖安装完成"

# 创建 Python 虚拟环境
log_info "创建 Python 虚拟环境..."
cd backend

if [ -d "venv" ]; then
    log_warning "虚拟环境已存在，是否重新创建? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf venv
        $PYTHON_CMD -m venv venv
        log_success "虚拟环境重新创建完成"
    else
        log_info "使用现有虚拟环境"
    fi
else
    $PYTHON_CMD -m venv venv
    log_success "虚拟环境创建完成"
fi

# 激活虚拟环境并安装依赖
log_info "安装 Python 依赖..."
source venv/bin/activate

# 升级 pip
pip install --upgrade pip > /dev/null 2>&1

# 安装依赖
pip install -r requirements.txt
log_success "Python 依赖安装完成"

# 显示 Python 环境信息
echo ""
log_info "Python 环境信息:"
echo "  Python: $(python --version)"
echo "  pip: $(pip --version | awk '{print $2}')"
echo "  虚拟环境: $(pwd)/venv"

deactivate
cd ..

echo ""

# ============================================================================
# 步骤 4: 下载 macOS 工具
# ============================================================================
log_header "步骤 4/6: 下载 macOS 工具"

TOOLS_BIN_DIR="$PROJECT_ROOT/resources/tools/bin"
mkdir -p "$TOOLS_BIN_DIR"

# 下载 ffmpeg (macOS)
if [ ! -f "$TOOLS_BIN_DIR/ffmpeg" ]; then
    log_info "下载 ffmpeg (macOS)..."
    FFMPEG_URL="https://evermeet.cx/ffmpeg/ffmpeg-7.1.zip"
    FFMPEG_ZIP="$TOOLS_BIN_DIR/ffmpeg.zip"
    
    if curl -L -o "$FFMPEG_ZIP" "$FFMPEG_URL"; then
        unzip -o "$FFMPEG_ZIP" -d "$TOOLS_BIN_DIR"
        rm -f "$FFMPEG_ZIP"
        chmod +x "$TOOLS_BIN_DIR/ffmpeg"
        log_success "ffmpeg 下载完成"
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
if [ ! -f "$TOOLS_BIN_DIR/yt-dlp" ]; then
    log_info "下载 yt-dlp (macOS)..."
    YTDLP_URL="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
    
    if curl -L -o "$TOOLS_BIN_DIR/yt-dlp" "$YTDLP_URL"; then
        chmod +x "$TOOLS_BIN_DIR/yt-dlp"
        log_success "yt-dlp 下载完成"
    else
        log_warning "yt-dlp 下载失败，将在运行时自动下载"
    fi
else
    log_success "yt-dlp 已存在"
fi

echo ""

# ============================================================================
# 步骤 5: 生成图标
# ============================================================================
log_header "步骤 5/6: 生成 macOS 图标"

if [ ! -f "resources/icon.icns" ]; then
    log_info "生成 .icns 图标..."
    node scripts/generate-icns.js

    if [ -f "resources/icon.icns" ]; then
        log_success "图标生成成功"
    else
        log_warning "图标生成失败，但不影响开发"
    fi
else
    log_success "图标已存在"
fi

echo ""

# ============================================================================
# 步骤 6: 验证环境
# ============================================================================
log_header "步骤 6/6: 环境验证"

ERRORS=0

# 检查关键文件
log_info "检查项目文件..."

if [ ! -f "package.json" ]; then
    log_error "package.json 不存在"
    ERRORS=$((ERRORS + 1))
fi

if [ ! -f "electron/main.js" ]; then
    log_error "electron/main.js 不存在"
    ERRORS=$((ERRORS + 1))
fi

if [ ! -d "frontend/dist" ]; then
    log_warning "前端未构建（开发模式下不需要）"
fi

if [ ! -d "backend/venv" ]; then
    log_error "Python 虚拟环境不存在"
    ERRORS=$((ERRORS + 1))
fi

if [ $ERRORS -eq 0 ]; then
    log_success "所有检查通过！"
else
    log_warning "发现 $ERRORS 个问题"
fi

echo ""

# ============================================================================
# 完成
# ============================================================================
log_header "🎉 环境初始化完成"
echo ""

log_info "下一步:"
echo "  📝 开发模式: ./scripts/dev-mac.sh"
echo "  📦 构建应用: ./scripts/build-mac.sh"
echo ""

log_info "快速命令:"
echo "  npm run dev         - 启动开发模式"
echo "  npm run build:mac   - 构建 macOS 应用"
echo ""

if [ "$IS_APPLE_SILICON" = true ]; then
    log_info "Apple Silicon 提示:"
    echo "  ✓ 项目已针对 M1/M2/M3 优化"
    echo "  ✓ AI 工具将使用 Metal GPU 加速"
    echo "  ✓ 构建会生成通用二进制（x64 + arm64）"
    echo ""
fi

log_success "环境已就绪，开始开发吧！🚀"
echo ""
