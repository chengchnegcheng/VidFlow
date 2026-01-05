"""
数据库配置和连接管理
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from pathlib import Path
import logging
import sys
import os

logger = logging.getLogger(__name__)

# 获取正确的数据目录（支持打包后的环境）
def get_data_dir() -> Path:
    """获取数据目录（与 main.py 保持一致）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的环境 - 使用用户数据目录
        if sys.platform == 'win32':
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            base_dir = Path(appdata) / 'VidFlow'
        elif sys.platform == 'darwin':
            base_dir = Path.home() / 'Library' / 'Application Support' / 'VidFlow'
        else:
            base_dir = Path.home() / '.local' / 'share' / 'VidFlow'
    else:
        # 开发环境
        base_dir = Path(__file__).parent.parent.parent
    
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

# 创建数据目录
DATA_DIR = get_data_dir()

# 数据库URL
DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR}/database.db"

# 创建异步引擎
# SQLite 特定配置：启用 WAL 模式以支持并发读写
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,  # SQLite 允许多线程
        "timeout": 60,  # 60秒超时（给予更多时间）
        "isolation_level": None,  # 自动提交模式，减少锁定时间
    },
    poolclass=NullPool,  # SQLite 使用 NullPool（每次创建新连接）
    pool_pre_ping=True,  # 连接前检查可用性
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 创建基类
Base = declarative_base()


async def init_database():
    """初始化数据库，创建所有表并启用 WAL 模式"""
    try:
        async with engine.begin() as conn:
            # 设置 UTF-8 编码（确保中文路径正确存储）
            await conn.execute(text("PRAGMA encoding='UTF-8'"))
            
            # 启用 WAL 模式（Write-Ahead Logging）
            # 允许多个读操作和一个写操作同时进行
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))  # 平衡性能和安全
            await conn.execute(text("PRAGMA busy_timeout=60000"))  # 60秒忙碌超时
            await conn.execute(text("PRAGMA cache_size=-32000"))  # 32MB 缓存
            await conn.execute(text("PRAGMA temp_store=MEMORY"))  # 临时表存储在内存
            await conn.execute(text("PRAGMA mmap_size=268435456"))  # 256MB 内存映射
            
            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)

            try:
                result = await conn.execute(text("PRAGMA table_info(subtitle_tasks)"))
                existing_cols = {row[1] for row in result.fetchall()}
                if "cancelled" not in existing_cols:
                    await conn.execute(
                        text("ALTER TABLE subtitle_tasks ADD COLUMN cancelled INTEGER NOT NULL DEFAULT 0")
                    )
                    logger.info("Migrated subtitle_tasks: added column 'cancelled'")
            except Exception as migrate_err:
                logger.warning(f"Schema migration skipped/failed: {migrate_err}")

            try:
                result = await conn.execute(text("PRAGMA table_info(burn_subtitle_tasks)"))
                existing_cols = {row[1] for row in result.fetchall()}
                if "cancelled" not in existing_cols:
                    await conn.execute(
                        text("ALTER TABLE burn_subtitle_tasks ADD COLUMN cancelled INTEGER NOT NULL DEFAULT 0")
                    )
                    logger.info("Migrated burn_subtitle_tasks: added column 'cancelled'")
            except Exception as migrate_err:
                logger.warning(f"Schema migration skipped/failed: {migrate_err}")
        
        logger.info("Database initialized successfully with WAL mode and UTF-8 encoding")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def get_session() -> AsyncSession:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
