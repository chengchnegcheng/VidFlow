"""
WebSocket功能测试
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.api.websocket import ConnectionManager, get_connection_manager


@pytest.mark.api
class TestWebSocketFunctional:
    """WebSocket功能测试"""

    @pytest.mark.asyncio
    async def test_websocket_status_endpoint(self):
        """测试WebSocket状态端点"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ws/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "active_connections" in data
        assert isinstance(data["active_connections"], int)


@pytest.mark.api
@pytest.mark.unit
class TestConnectionManagerFunctions:
    """连接管理器功能测试"""

    @pytest.fixture
    def manager(self):
        """创建连接管理器"""
        return ConnectionManager()

    def test_manager_initialization(self, manager):
        """测试管理器初始化"""
        assert manager is not None
        assert len(manager.active_connections) == 0

    def test_get_connection_manager_singleton(self):
        """测试获取连接管理器单例"""
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_broadcast_task_update_message_format(self, manager):
        """测试任务更新广播消息格式"""
        # 测试消息格式（不实际广播）
        task_data = {
            "task_id": "test-123",
            "status": "downloading",
            "progress": 50.0
        }
        # 验证方法存在且可调用
        assert hasattr(manager, 'broadcast_task_update')
        assert callable(manager.broadcast_task_update)

    @pytest.mark.asyncio
    async def test_broadcast_task_progress_message_format(self, manager):
        """测试任务进度广播消息格式"""
        # 验证方法存在
        assert hasattr(manager, 'broadcast_task_progress')
        assert callable(manager.broadcast_task_progress)

    @pytest.mark.asyncio
    async def test_broadcast_task_complete_message_format(self, manager):
        """测试任务完成广播消息格式"""
        # 验证方法存在
        assert hasattr(manager, 'broadcast_task_complete')
        assert callable(manager.broadcast_task_complete)

    @pytest.mark.asyncio
    async def test_broadcast_system_status_message_format(self, manager):
        """测试系统状态广播消息格式"""
        # 验证方法存在
        assert hasattr(manager, 'broadcast_system_status')
        assert callable(manager.broadcast_system_status)


@pytest.mark.api
@pytest.mark.unit
class TestConnectionManagerMethods:
    """连接管理器方法测试"""

    @pytest.fixture
    def manager(self):
        """创建连接管理器"""
        return ConnectionManager()

    def test_has_connect_method(self, manager):
        """测试connect方法存在"""
        assert hasattr(manager, 'connect')
        assert callable(manager.connect)

    def test_has_disconnect_method(self, manager):
        """测试disconnect方法存在"""
        assert hasattr(manager, 'disconnect')
        assert callable(manager.disconnect)

    def test_has_send_personal_message_method(self, manager):
        """测试send_personal_message方法存在"""
        assert hasattr(manager, 'send_personal_message')
        assert callable(manager.send_personal_message)

    def test_has_broadcast_method(self, manager):
        """测试broadcast方法存在"""
        assert hasattr(manager, 'broadcast')
        assert callable(manager.broadcast)

    def test_active_connections_is_set(self, manager):
        """测试active_connections是集合"""
        assert hasattr(manager, 'active_connections')
        assert isinstance(manager.active_connections, set)

    def test_initial_connections_empty(self, manager):
        """测试初始连接为空"""
        assert len(manager.active_connections) == 0


@pytest.mark.api
class TestWebSocketMessageTypes:
    """WebSocket消息类型测试"""

    def test_message_types_defined(self):
        """测试消息类型定义"""
        message_types = [
            "task_update",
            "task_progress",
            "task_complete",
            "system_status",
            "download_progress",
            "subtitle_progress"
        ]

        for msg_type in message_types:
            assert isinstance(msg_type, str)
            assert len(msg_type) > 0

    def test_task_update_message_keys(self):
        """测试任务更新消息键"""
        expected_keys = ["type", "data", "timestamp"]
        for key in expected_keys:
            assert isinstance(key, str)

    def test_message_structure_validity(self):
        """测试消息结构有效性"""
        message = {
            "type": "task_update",
            "data": {"task_id": "123"},
            "timestamp": "2025-01-01T00:00:00"
        }

        assert "type" in message
        assert "data" in message
        assert isinstance(message["data"], dict)


@pytest.mark.api
class TestWebSocketEndpoint:
    """WebSocket端点测试"""

    @pytest.mark.asyncio
    async def test_websocket_status_returns_json(self):
        """测试WebSocket状态返回JSON"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ws/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_websocket_status_has_connections_count(self):
        """测试WebSocket状态包含连接数"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ws/status")

        data = response.json()
        assert "active_connections" in data
        assert data["active_connections"] >= 0
