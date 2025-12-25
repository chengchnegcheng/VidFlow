"""
VidFlow Backend - FastAPI Application
"""
# ============================================
# pip 模式支持（必须在最开始，用于 PyInstaller 打包后）
# ============================================
import sys
import os

# 如果参数是 -m pip，直接运行 pip 模块然后退出
if len(sys.argv) >= 2 and sys.argv[1] == '-m' and len(sys.argv) >= 3 and sys.argv[2] == 'pip':
    import runpy
    # 移除 -m pip，保留后续参数
    sys.argv = ['pip'] + sys.argv[3:]
    runpy.run_module('pip', run_name='__main__')
    sys.exit(0)

# ============================================
# 强制 UTF-8 编码
# ============================================
# 设置默认编码为 UTF-8
if sys.platform == 'win32':
    # Windows 特殊处理
    import locale
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

    # 重新配置 stdout/stderr 为 UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ============================================
# 导入其他模块
# ============================================
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import shutil
import asyncio
import uvicorn
import subprocess
import platform
import psutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

# 获取正确的基础目录（支持打包后的环境）
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后的环境
    # 使用用户数据目录作为基础目录（可写）
    if sys.platform == 'win32':
        # Windows: 使用 AppData/Roaming/VidFlow
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        BASE_DIR = Path(appdata) / 'VidFlow'
    elif sys.platform == 'darwin':
        # macOS: 使用 ~/Library/Application Support/VidFlow
        BASE_DIR = Path.home() / 'Library' / 'Application Support' / 'VidFlow'
    else:
        # Linux: 使用 ~/.local/share/VidFlow
        BASE_DIR = Path.home() / '.local' / 'share' / 'VidFlow'

    # 确保目录存在
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📦 Running in packaged mode, data directory: {BASE_DIR}")
else:
    # 开发环境
    BASE_DIR = Path(__file__).parent.parent

# 将 backend 目录添加到 Python 路径
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 导入配置管理器（必须在 sys.path 设置之后）
from src.core.config_manager import get_config_manager

# 提前检查 Python 版本（AI 依赖兼容性）
python_version = sys.version_info
if python_version.major == 3 and python_version.minor >= 12:
    _py_warn_lines = [
        f"⚠️ Python {python_version.major}.{python_version.minor} detected",
        "⚠️ AI features (faster-whisper) require Python 3.8-3.11",
        "⚠️ Please create a virtual environment with Python 3.11 before enabling AI features",
    ]
    for _line in _py_warn_lines:
        print(_line)
        logging.warning(_line)

# 检查运行环境
print(f"🐍 Python Executable: {sys.executable}")
print(f"🐍 Python Version: {sys.version.split()[0]}")
in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
print(f"📦 In Virtual Environment: {in_venv}")
if in_venv:
    print(f"📦 Virtual Environment: {sys.prefix}")

DATA_DIR = BASE_DIR / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"
LOGS_DIR = DATA_DIR / "logs"

for directory in [DATA_DIR, DOWNLOAD_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

print(f"BASE_DIR: {BASE_DIR}")
print(f"DATA_DIR: {DATA_DIR}")
print(f"LOGS_DIR: {LOGS_DIR}")

# 配置日志（UTF-8 已在程序开始处配置）
log_file_path = LOGS_DIR / "app.log"
print(f"📝 Log file path: {log_file_path}")

# 确保日志文件可以被创建
try:
    # 测试写入权限
    with open(log_file_path, 'a', encoding='utf-8') as test_file:
        test_file.write(f"\n=== Backend starting at {datetime.now()} ===\n")
    print(f"✅ Log file is writable")
except Exception as e:
    print(f"❌ Cannot write to log file: {e}")

file_handler = RotatingFileHandler(
    log_file_path,
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding='utf-8',
)
stream_handler = logging.StreamHandler(sys.stdout)

# 支持通过环境变量或配置文件配置日志等级/格式
config_manager = get_config_manager()
log_level_raw = os.environ.get("LOG_LEVEL") or config_manager.get("advanced.log_level", "INFO")
log_format = os.environ.get("LOG_FORMAT") or config_manager.get(
    "advanced.log_format",
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
LOG_LEVEL = str(log_level_raw).upper()
valid_levels = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
logging.basicConfig(
    level=valid_levels.get(LOG_LEVEL, logging.INFO),
    format=log_format,
    handlers=[file_handler, stream_handler]
)

logger = logging.getLogger(__name__)

# Lifespan 事件管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    startup_start_time = time.time()
    logger.info("Backend startup initiated")

    # 启动时执行 - 只做最必要的同步初始化
    from src.models import Base, init_database
    await init_database()
    logger.info("Database initialized")

    # 所有耗时操作都放到后台异步执行,不阻塞API启动
    # 这样可以让健康检查和API立即可用,提升用户体验

    # 清理旧的进行中任务（后台任务，不阻塞启动）
    asyncio.create_task(cleanup_stale_tasks())

    # 初始化工具（后台任务，不阻塞启动）
    from src.core.tool_manager import initialize_tools
    asyncio.create_task(initialize_tools())

    # 预热AI状态缓存（后台任务，不阻塞启动）
    def preload_ai_cache():
        from src.api.system import _preload_ai_status_cache
        _preload_ai_status_cache()

    asyncio.create_task(asyncio.to_thread(preload_ai_cache))

    # 启动数据库备份调度任务（后台任务，不阻塞启动）
    from src.core.backup_manager import schedule_backup_task
    backup_task = asyncio.create_task(
        schedule_backup_task(
            db_path=DATA_DIR / "database.db",
            backup_dir=DATA_DIR / "backups",
            interval_hours=24  # 每24小时备份一次
        )
    )
    logger.info("Database backup scheduler started (interval: 24 hours)")

    startup_duration = time.time() - startup_start_time
    logger.info(f"✅ Backend startup completed in {startup_duration:.3f}s, ready to accept requests")

    yield

    # 关闭时执行 - 停止所有进行中的任务
    await stop_all_active_tasks()

    # 停止备份调度任务
    if 'backup_task' in locals() and not backup_task.done():
        backup_task.cancel()
        try:
            await backup_task
        except asyncio.CancelledError:
            pass
        logger.info("Database backup scheduler stopped")

    logger.info("Application shutdown")


async def cleanup_stale_tasks():
    """清理旧的进行中任务（应用启动时）"""
    try:
        logger.info("Starting cleanup of stale tasks...")
        from src.models.database import AsyncSessionLocal
        from src.models.subtitle import SubtitleTask, BurnSubtitleTask
        from src.models.download import DownloadTask
        from sqlalchemy import select
        from datetime import datetime
        
        total_cleaned = 0
        
        # 分别处理每种任务类型，每个使用独立的会话和事务
        for model, statuses in [
            (SubtitleTask, ['pending', 'processing']),
            (BurnSubtitleTask, ['pending', 'burning']),
            (DownloadTask, ['pending', 'downloading'])
        ]:
            try:
                # 每个任务类型使用独立的会话，避免长时间持有锁
                async with AsyncSessionLocal() as session:
                    stmt = select(model).where(model.status.in_(statuses))
                    result = await session.execute(stmt)
                    tasks = result.scalars().all()
                    
                    if tasks:
                        for task in tasks:
                            task.status = 'failed'
                            task.error = '应用意外关闭，任务已取消'
                            task.completed_at = datetime.utcnow()
                            logger.debug(f"Cleaned up stale {model.__name__} task: {task.id}")
                        
                        # 立即提交并关闭会话
                        await session.commit()
                        total_cleaned += len(tasks)
                        logger.debug(f"Committed {len(tasks)} {model.__name__} tasks")
                    
            except Exception as e:
                logger.error(f"Error cleaning {model.__name__}: {e}")
        
        if total_cleaned > 0:
            logger.info(f"✅ Cleaned up {total_cleaned} stale tasks")
        else:
            logger.info("✅ No stale tasks to clean up")
                
    except Exception as e:
        logger.error(f"❌ Failed to cleanup stale tasks: {e}", exc_info=True)


async def stop_all_active_tasks():
    """停止所有进行中的任务（应用关闭时）"""
    try:
        from src.models.database import AsyncSessionLocal
        from src.models.subtitle import SubtitleTask, BurnSubtitleTask
        from src.models.download import DownloadTask
        from sqlalchemy import select
        from datetime import datetime
        
        async with AsyncSessionLocal() as session:
            # 停止所有进行中的任务
            for model in [SubtitleTask, BurnSubtitleTask, DownloadTask]:
                stmt = select(model).where(
                    model.status.in_(['pending', 'processing', 'downloading', 'burning'])
                )
                result = await session.execute(stmt)
                tasks = result.scalars().all()
                
                for task in tasks:
                    task.status = 'failed'
                    task.error = '应用正常关闭，任务已停止'
                    task.completed_at = datetime.utcnow()
                    logger.info(f"Stopped task on shutdown: {task.id}")
            
            await session.commit()
            logger.info("✅ All active tasks stopped")
            
    except Exception as e:
        logger.error(f"Failed to stop active tasks: {e}")

# 创建 FastAPI 应用
app = FastAPI(
    title="VidFlow API",
    description="全能视频下载器 API",
    version="1.0.2",
    lifespan=lifespan
)

# 请求计时中间件 - 监控慢查询
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # 记录慢请求（超过1秒）
    if process_time > 1.0:
        logger.warning(f"⚠️ Slow request: {request.method} {request.url.path} took {process_time:.2f}s")
    
    response.headers["X-Process-Time"] = str(process_time)
    return response

# 配置 CORS - 开发环境允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 导入路由
from src.api import downloads, system, websocket, subtitle, logs, config, proxy

# 注册路由
app.include_router(downloads.router)
app.include_router(system.router)
app.include_router(websocket.router)
app.include_router(subtitle.router)
app.include_router(logs.router)
app.include_router(config.router)
app.include_router(proxy.router)

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "VidFlow API Server",
        "version": app.version,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "backend": "ready",
        "timestamp": datetime.now().isoformat()
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"Global exception: {exc}", exc_info=True)

    is_dev = os.getenv("ENV", "production") == "development"

    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc) if is_dev else "服务器内部错误",
            "type": type(exc).__name__ if is_dev else "InternalServerError"
        }
    )

if __name__ == "__main__":
    import uvicorn
    import socket
    import json
    import sys
    
    print("=" * 60, flush=True)
    print("🚀 VidFlow Backend Starting...", flush=True)
    print("=" * 60, flush=True)
    
    logger.info("Starting VidFlow Backend Server...")
    logger.info(f"Data directory: {DATA_DIR}")
    logger.info(f"Download directory: {DOWNLOAD_DIR}")
    
    print(f"📁 Data directory: {DATA_DIR}", flush=True)
    print(f"📥 Download directory: {DOWNLOAD_DIR}", flush=True)
    
    # 检查是否指定固定端口（用于浏览器开发模式）
    fixed_port = os.environ.get('VIDFLOW_FIXED_PORT')
    
    if fixed_port:
        # 浏览器模式：使用固定端口
        try:
            port = int(fixed_port)
            logger.info(f"Using fixed port {port} for browser development mode")
        except ValueError:
            logger.error(f"Invalid fixed port: {fixed_port}, using random port")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
            sock.close()
    else:
        # Electron 模式：使用随机端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        logger.info(f"Using random port {port} for Electron mode")
    
    # 将端口信息写入文件供 Electron 读取
    port_file = DATA_DIR / "backend_port.json"
    with open(port_file, 'w') as f:
        json.dump({"port": port, "host": "127.0.0.1"}, f)
    
    print("=" * 60, flush=True)
    print(f"✅ Port file written: {port_file}", flush=True)
    print(f"🌐 Server will start on port: {port}", flush=True)
    print(f"📡 Backend URL: http://127.0.0.1:{port}", flush=True)
    print("=" * 60, flush=True)
    
    logger.info(f"Server will start on port: {port}")
    logger.info(f"Port file: {port_file}")
    
    # 确保所有输出都被刷新
    sys.stdout.flush()
    sys.stderr.flush()
    
    print(f"Starting Uvicorn on http://127.0.0.1:{port} ...", flush=True)
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=True
    )
