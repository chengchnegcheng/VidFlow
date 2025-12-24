"""
WebSocket 管理器测试
"""
import pytest
from src.core.websocket_manager import WebSocketManager, get_ws_manager


class TestWebSocketManager:
    """WebSocket 管理器测试"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = get_ws_manager()
        manager2 = get_ws_manager()
        assert manager1 is manager2, "应该返回同一个实例"
    
    def test_manager_initialization(self):
        """测试管理器初始化"""
        manager = WebSocketManager()
        assert isinstance(manager.active_connections, set)
        assert len(manager.active_connections) == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_message_format(self):
        """测试广播消息格式"""
        manager = WebSocketManager()
        
        # 测试工具进度消息格式
        message = {
            "type": "tool_install_progress",
            "tool_id": "ffmpeg",
            "progress": 50,
            "message": "下载中..."
        }
        
        # 应该不抛出异常（没有连接时）
        await manager.broadcast(message)
    
    @pytest.mark.asyncio
    async def test_send_tool_progress(self):
        """测试发送工具进度"""
        manager = WebSocketManager()
        
        # 应该不抛出异常
        await manager.send_tool_progress("ffmpeg", 50, "下载中...")
        await manager.send_tool_progress("ytdlp", 100, "安装完成")
    
    @pytest.mark.asyncio
    async def test_send_notification(self):
        """测试发送通知"""
        manager = WebSocketManager()
        
        await manager.send_notification("测试", "消息内容", "info")
        await manager.send_notification("错误", "错误内容", "error")


class TestWebSocketManagerEdgeCases:
    """WebSocket 管理器边界测试"""
    
    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self):
        """测试空连接列表广播"""
        manager = WebSocketManager()
        
        # 应该能处理空连接
        await manager.broadcast({"type": "test"})
        assert len(manager.active_connections) == 0
    
    @pytest.mark.asyncio
    async def test_progress_values(self):
        """测试进度值范围"""
        manager = WebSocketManager()
        
        # 测试边界值
        await manager.send_tool_progress("test", 0, "开始")
        await manager.send_tool_progress("test", 50, "中间")
        await manager.send_tool_progress("test", 100, "完成")
