"""
WebSocket 管理器 - 处理实时消息推送
"""
import logging
from typing import Dict, Set
from fastapi import WebSocket
import json

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # 存储所有活跃的 WebSocket 连接
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """断开 WebSocket 连接并关闭通道"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        try:
            await websocket.close()
        except Exception as e:
            logger.warning(f"Failed to close websocket: {e}")
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """发送消息给特定连接"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
    
    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        logger.info(f"Broadcasting message to {len(self.active_connections)} connections: {message}")
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast message: {e}")
                disconnected.add(connection)

        # 清理断开的连接（只从集合中移除，不尝试关闭）
        for connection in disconnected:
            if connection in self.active_connections:
                self.active_connections.remove(connection)
                logger.info(f"Removed disconnected WebSocket. Total connections: {len(self.active_connections)}")
    
    async def send_message(self, message: dict):
        """发送任意消息（通用广播）"""
        await self.broadcast(message)
    
    async def send_tool_progress(self, tool_id: str, progress: int, message: str):
        """发送工具安装进度"""
        await self.broadcast({
            "type": "tool_install_progress",
            "tool_id": tool_id,
            "progress": progress,
            "message": message
        })

    async def send_tool_error(self, tool_id: str, error: str):
        """发送工具安装错误"""
        await self.broadcast({
            "type": "tool_install_error",
            "tool_id": tool_id,
            "error": error
        })
    
    async def send_download_progress(self, task_id: str, progress: dict):
        """发送下载进度"""
        await self.broadcast({
            "type": "download_progress",
            "task_id": task_id,
            **progress
        })
    
    async def send_subtitle_progress(self, task_id: str, progress: dict):
        """发送字幕生成进度"""
        await self.broadcast({
            "type": "subtitle_progress",
            "task_id": task_id,
            **progress
        })
    
    async def send_burn_progress(self, task_id: str, progress: dict):
        """发送字幕烧录进度"""
        await self.broadcast({
            "type": "burn_progress",
            "task_id": task_id,
            **progress
        })
    
    async def send_notification(self, title: str, message: str, level: str = "info"):
        """发送通知消息"""
        await self.broadcast({
            "type": "notification",
            "title": title,
            "message": message,
            "level": level
        })

# 全局 WebSocket 管理器实例
ws_manager = WebSocketManager()

def get_ws_manager() -> WebSocketManager:
    """获取 WebSocket 管理器实例"""
    return ws_manager
