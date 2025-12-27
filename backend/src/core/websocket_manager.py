"""
WebSocket 管理器 - 处理实时消息推送
"""
import logging
import time
from typing import Dict, Set, Optional, Tuple
from fastapi import WebSocket
import json

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 存储所有活跃的 WebSocket 连接
        self.active_connections: Set[WebSocket] = set()
        # 消息节流：记录最近发送的消息和时间戳
        # key: message_key, value: (timestamp, last_logged_timestamp)
        self._last_broadcast: Dict[str, Tuple[float, float]] = {}
        # 节流配置
        self.MIN_BROADCAST_INTERVAL = 0.5  # 最小广播间隔（秒）
        self.LOG_THROTTLE_INTERVAL = 2.0   # 日志节流间隔（秒）
        self.MAX_CACHE_SIZE = 100          # 最大缓存条目数
        self._last_cleanup = time.time()
        self.CLEANUP_INTERVAL = 60         # 清理间隔（秒）

    def _cleanup_old_cache(self):
        """清理过期的缓存条目"""
        current_time = time.time()

        # 每分钟清理一次
        if current_time - self._last_cleanup < self.CLEANUP_INTERVAL:
            return

        self._last_cleanup = current_time

        # 删除 5 分钟前的条目
        MAX_AGE = 300
        expired_keys = [
            key for key, (timestamp, _) in self._last_broadcast.items()
            if current_time - timestamp > MAX_AGE
        ]

        for key in expired_keys:
            del self._last_broadcast[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired broadcast cache entries")

        # 如果缓存仍然太大，删除最旧的条目
        if len(self._last_broadcast) > self.MAX_CACHE_SIZE:
            sorted_items = sorted(
                self._last_broadcast.items(),
                key=lambda x: x[1][0]  # 按时间戳排序
            )
            # 保留最新的 MAX_CACHE_SIZE 条目
            items_to_remove = len(self._last_broadcast) - self.MAX_CACHE_SIZE
            for key, _ in sorted_items[:items_to_remove]:
                del self._last_broadcast[key]

            logger.debug(f"Removed {items_to_remove} oldest broadcast cache entries")

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

    async def broadcast(self, message: dict, skip_throttle: bool = False):
        """
        广播消息给所有连接

        Args:
            message: 要广播的消息
            skip_throttle: 是否跳过节流检查（用于重要消息）
        """
        # 定期清理缓存
        self._cleanup_old_cache()

        # 生成消息的唯一键（用于节流）
        message_type = message.get("type", "unknown")
        if message_type == "tool_install_progress":
            # 工具进度消息：按 tool_id + progress 分组
            tool_id = message.get("tool_id", "")
            progress = message.get("progress", 0)
            message_key = f"{message_type}:{tool_id}:{progress}"
        elif message_type in ("download_progress", "subtitle_progress", "burn_progress"):
            # 任务进度消息：按 task_id + status 分组
            task_id = message.get("task_id", "")
            status = message.get("status", "")
            message_key = f"{message_type}:{task_id}:{status}"
        else:
            # 其他消息：按类型分组
            message_key = message_type

        # 检查是否需要节流
        current_time = time.time()
        should_broadcast = skip_throttle
        should_log = skip_throttle

        if not skip_throttle and message_key in self._last_broadcast:
            last_broadcast_time, last_logged_time = self._last_broadcast[message_key]

            # 检查是否满足最小广播间隔
            if current_time - last_broadcast_time < self.MIN_BROADCAST_INTERVAL:
                return  # 跳过此次广播

            # 检查是否需要记录日志
            should_log = (current_time - last_logged_time >= self.LOG_THROTTLE_INTERVAL)
        else:
            should_broadcast = True
            should_log = True

        # 记录日志（节流）
        if should_log:
            logger.info(f"Broadcasting to {len(self.active_connections)} connections: {message}")
            self._last_broadcast[message_key] = (current_time, current_time)
        else:
            # 更新广播时间，但不更新日志时间
            _, last_logged_time = self._last_broadcast.get(message_key, (0, 0))
            self._last_broadcast[message_key] = (current_time, last_logged_time)

        # 广播消息
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
        }, skip_throttle=True)  # 错误消息不节流

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
        }, skip_throttle=True)  # 通知消息不节流

# 全局 WebSocket 管理器实例
ws_manager = WebSocketManager()

def get_ws_manager() -> WebSocketManager:
    """获取 WebSocket 管理器实例"""
    return ws_manager
