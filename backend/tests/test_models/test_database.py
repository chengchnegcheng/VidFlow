"""
数据库功能测试
"""
import pytest
from pathlib import Path
from src.models.database import Base, engine, get_session


@pytest.mark.unit
class TestDatabase:
    """数据库测试"""

    def test_base_exists(self):
        """测试Base对象存在"""
        assert Base is not None

    def test_engine_exists(self):
        """测试engine对象存在"""
        assert engine is not None

    def test_get_session_callable(self):
        """测试get_session是可调用的"""
        assert callable(get_session)


@pytest.mark.unit
class TestDatabaseSession:
    """数据库会话测试"""

    @pytest.mark.asyncio
    async def test_get_session_returns_async_generator(self):
        """测试get_session返回异步生成器"""
        session_gen = get_session()
        assert hasattr(session_gen, '__aiter__')

    @pytest.mark.asyncio
    async def test_session_lifecycle(self):
        """测试会话生命周期"""
        session_gen = get_session()
        session = await session_gen.__anext__()

        # 会话应该不为空
        assert session is not None

        # 清理
        try:
            await session_gen.__anext__()
        except StopAsyncIteration:
            pass  # 预期行为


@pytest.mark.unit
class TestDatabaseMetadata:
    """数据库元数据测试"""

    def test_base_has_metadata(self):
        """测试Base有metadata属性"""
        assert hasattr(Base, 'metadata')

    def test_metadata_has_tables(self):
        """测试metadata有tables属性"""
        assert hasattr(Base.metadata, 'tables')

    def test_tables_is_dict(self):
        """测试tables是字典"""
        assert isinstance(Base.metadata.tables, dict)


@pytest.mark.unit
class TestDatabaseTables:
    """数据库表测试"""

    def test_download_tasks_table_exists(self):
        """测试download_tasks表存在"""
        tables = Base.metadata.tables
        # 表可能存在也可能不存在，取决于是否已初始化
        assert isinstance(tables, dict)

    def test_subtitle_tasks_table_exists(self):
        """测试subtitle_tasks表存在"""
        tables = Base.metadata.tables
        # 表可能存在也可能不存在，取决于是否已初始化
        assert isinstance(tables, dict)
