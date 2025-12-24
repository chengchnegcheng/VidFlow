"""
Pytest 配置和 Fixtures
"""
import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport

from src.models.database import Base
from src.main import app


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话"""
    # 使用内存数据库
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建会话
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    # 清理
    await engine.dispose()


@pytest.fixture
def mock_video_info():
    """模拟视频信息"""
    return {
        "title": "Test Video",
        "url": "https://www.youtube.com/watch?v=test123",
        "platform": "youtube",
        "duration": 120,
        "thumbnail": "https://example.com/thumb.jpg",
        "formats": [
            {
                "format_id": "18",
                "ext": "mp4",
                "quality": "360p",
                "filesize": 10485760
            },
            {
                "format_id": "22",
                "ext": "mp4", 
                "quality": "720p",
                "filesize": 52428800
            }
        ]
    }


@pytest.fixture
def sample_download_task():
    """示例下载任务数据"""
    return {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "quality": "best",
        "output_path": None,
        "format_id": None
    }


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """创建测试客户端"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
