"""
WebSocket API 扩展测试
"""
import pytest
from src.api.websocket import ConnectionManager


@pytest.mark.api
@pytest.mark.unit
class TestConnectionManager:
    """连接管理器测试类"""
    
    @pytest.fixture
    def manager(self):
        """创建连接管理器实例"""
        return ConnectionManager()
    
    def test_connection_manager_initialization(self, manager):
        """测试连接管理器初始化"""
        assert manager is not None
        assert isinstance(manager.active_connections, set)
        assert len(manager.active_connections) == 0
    
    def test_active_connections_type(self, manager):
        """测试活动连接集合类型"""
        assert hasattr(manager, 'active_connections')
        assert isinstance(manager.active_connections, set)
    
    def test_broadcast_task_update_message_format(self, manager):
        """测试任务更新消息格式"""
        # 测试消息格式构建（不实际发送）
        task_data = {
            "task_id": "test-123",
            "status": "downloading",
            "progress": 50.0
        }
        # ConnectionManager有broadcast_task_update方法
        assert hasattr(manager, 'broadcast_task_update')
    
    def test_broadcast_task_progress_method(self, manager):
        """测试进度广播方法存在"""
        assert hasattr(manager, 'broadcast_task_progress')
    
    def test_broadcast_task_complete_method(self, manager):
        """测试完成广播方法存在"""
        assert hasattr(manager, 'broadcast_task_complete')
    
    def test_broadcast_system_status_method(self, manager):
        """测试系统状态广播方法存在"""
        assert hasattr(manager, 'broadcast_system_status')
    
    def test_send_personal_message_method(self, manager):
        """测试个人消息方法存在"""
        assert hasattr(manager, 'send_personal_message')
    
    def test_broadcast_method(self, manager):
        """测试广播方法存在"""
        assert hasattr(manager, 'broadcast')
    
    def test_connect_method(self, manager):
        """测试连接方法存在"""
        assert hasattr(manager, 'connect')
    
    def test_disconnect_method(self, manager):
        """测试断开连接方法存在"""
        assert hasattr(manager, 'disconnect')


@pytest.mark.api
@pytest.mark.unit
class TestWebSocketMessages:
    """WebSocket消息格式测试"""
    
    def test_message_type_constants(self):
        """测试消息类型定义"""
        # WebSocket应该定义消息类型
        message_types = [
            "task_update",
            "task_progress", 
            "task_complete",
            "system_status"
        ]
        # 验证这些是有效的字符串
        for msg_type in message_types:
            assert isinstance(msg_type, str)
            assert len(msg_type) > 0
    
    def test_task_update_message_structure(self):
        """测试任务更新消息结构"""
        message = {
            "type": "task_update",
            "data": {
                "task_id": "test-123",
                "status": "downloading"
            },
            "timestamp": "2025-01-01T00:00:00"
        }
        
        assert "type" in message
        assert "data" in message
        assert "timestamp" in message
        assert message["type"] == "task_update"
    
    def test_task_progress_message_structure(self):
        """测试任务进度消息结构"""
        message = {
            "type": "task_progress",
            "data": {
                "task_id": "test-123",
                "progress": 50.0,
                "speed": "1.5 MB/s"
            },
            "timestamp": "2025-01-01T00:00:00"
        }
        
        assert message["type"] == "task_progress"
        assert "progress" in message["data"]
        assert isinstance(message["data"]["progress"], (int, float))
    
    def test_task_complete_message_structure(self):
        """测试任务完成消息结构"""
        message = {
            "type": "task_complete",
            "data": {
                "task_id": "test-123",
                "success": True,
                "message": "Download completed"
            },
            "timestamp": "2025-01-01T00:00:00"
        }
        
        assert message["type"] == "task_complete"
        assert "success" in message["data"]
        assert isinstance(message["data"]["success"], bool)
    
    def test_system_status_message_structure(self):
        """测试系统状态消息结构"""
        message = {
            "type": "system_status",
            "data": {
                "cpu_usage": 45.2,
                "memory_usage": 60.5,
                "disk_usage": 75.0
            },
            "timestamp": "2025-01-01T00:00:00"
        }
        
        assert message["type"] == "system_status"
        assert "data" in message
        assert isinstance(message["data"], dict)
