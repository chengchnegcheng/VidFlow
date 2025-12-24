"""
WebSocket API - 实时通信
"""
import json
import asyncio
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime
import logging
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """接受新连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """断开连接并关闭连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        try:
            await websocket.close()
        except Exception as e:
            logger.warning(f"Failed to close websocket: {e}")
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast message: {e}")
                disconnected.add(connection)
        
        # 移除断开的连接
        for connection in disconnected:
            await self.disconnect(connection)
    
    async def broadcast_task_update(self, task_data: dict):
        """广播任务更新"""
        message = {
            "type": "task_update",
            "data": task_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def broadcast_task_progress(self, task_id: str, progress: float, speed: str = ""):
        """广播任务进度"""
        message = {
            "type": "task_progress",
            "data": {
                "task_id": task_id,
                "progress": progress,
                "speed": speed
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def broadcast_task_complete(self, task_id: str, success: bool, message_text: str = ""):
        """广播任务完成"""
        message = {
            "type": "task_complete",
            "data": {
                "task_id": task_id,
                "success": success,
                "message": message_text
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def broadcast_system_status(self, status_data: dict):
        """广播系统状态"""
        message = {
            "type": "system_status",
            "data": status_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)

# 全局连接管理器
manager = ConnectionManager()

MAX_MESSAGE_SIZE = 10 * 1024  # 10KB


class WebSocketMessage(BaseModel):
    type: str
    data: dict = {}

    @validator("type")
    def validate_type(cls, v: str) -> str:
        allowed_types = {"ping", "subscribe", "unsubscribe"}
        if v not in allowed_types:
            raise ValueError(f"Invalid message type: {v}")
        return v

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 主端点"""
    await manager.connect(websocket)
    
    try:
        # 发送欢迎消息
        await manager.send_personal_message({
            "type": "connection",
            "message": "Connected to VidFlow WebSocket",
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        # 保持连接并处理消息
        while True:
            data = await websocket.receive_text()
            if len(data) > MAX_MESSAGE_SIZE:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Message too large",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                continue
            
            try:
                parsed = WebSocketMessage.parse_raw(data)
                message_type = parsed.type
                
                # 处理不同类型的消息
                if message_type == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                
                elif message_type == "subscribe":
                    # 订阅特定事件
                    events = parsed.data.get("events", [])
                    await manager.send_personal_message({
                        "type": "subscribed",
                        "events": events,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                
                else:
                    # 未知消息类型
                    await manager.send_personal_message({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
            
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
            except Exception as e:
                logger.warning(f"Invalid WebSocket message: {e}")
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Invalid message format",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.info("Client disconnected normally")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await manager.disconnect(websocket)


@router.websocket("/v1/events")
async def websocket_events(websocket: WebSocket):
    """
    兼容前端 ws://.../v1/events?token=... 的连接。
    复用同一处理逻辑（当前未校验 token）。
    """
    await websocket_endpoint(websocket)

@router.get("/ws/status")
async def get_websocket_status():
    """获取 WebSocket 状态"""
    return {
        "active_connections": len(manager.active_connections),
        "status": "running"
    }

# 导出 manager 供其他模块使用
def get_connection_manager() -> ConnectionManager:
    """获取连接管理器实例"""
    return manager
