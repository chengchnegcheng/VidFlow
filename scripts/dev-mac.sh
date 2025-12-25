#!/bin/bash
################################################################################
# VidFlow macOS 开发模式启动脚本
# 自动启动前端、后端和 Electron 开发环境
################################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 获取脚本所在目录的上级目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." &> /dev/null && pwd )"

cd "$PROJECT_ROOT"

log_header "VidFlow 开发模式启动"
log_info "项目路径: $PROJECT_ROOT"
log_info "平台: macOS ($(uname -m))"
echo ""

# ============================================================================
# 环境检查
# ============================================================================
log_header "环境检查"

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
log_success "Python: $(python3 --version)"

# 检查依赖是否已安装
echo ""
log_info "检查依赖..."

if [ ! -d "node_modules" ]; then
    log_warning "根目录依赖未安装"
    log_info "正在安装依赖..."
    npm install
    log_success "依赖安装完成"
fi

if [ ! -d "frontend/node_modules" ]; then
    log_warning "前端依赖未安装"
    log_info "正在安装前端依赖..."
    cd frontend
    npm install
    cd ..
    log_success "前端依赖安装完成"
fi

if [ ! -d "backend/venv" ]; then
    log_warning "Python 虚拟环境未创建"
    log_info "正在创建虚拟环境..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate

    log_info "安装 Python 依赖..."
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r requirements.txt

    log_success "Python 环境创建完成"
    deactivate
    cd ..
fi

log_success "所有依赖已就绪"

echo ""
log_header "启动开发服务器"
echo ""

log_info "即将启动以下服务:"
echo "  🔹 后端服务 (FastAPI): http://127.0.0.1:8000"
echo "  🔹 前端服务 (Vite): http://localhost:5173"
echo "  🔹 Electron 主进程"
echo ""

log_warning "提示: 按 Ctrl+C 停止所有服务"
echo ""

# 等待用户确认
read -p "按 Enter 键开始，或按 Ctrl+C 取消..." -r

# ============================================================================
# 清理旧的端口文件
# ============================================================================
if [ -f "frontend_port.json" ]; then
    rm -f frontend_port.json
fi

if [ -f "backend/data/backend_port.json" ]; then
    rm -f backend/data/backend_port.json
fi

# ============================================================================
# 启动开发模式
# ============================================================================
echo ""
log_info "启动开发服务器..."
echo ""

# 使用 npm 的 dev 脚本（会自动启动所有服务）
npm run dev

# 注意: npm run dev 使用 concurrently 并发运行多个进程
# 当用户按 Ctrl+C 时，所有子进程都会被终止
