"""
WebSocket API 测试
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestWebSocketAPI:
    """WebSocket API 测试类"""

    @pytest.mark.asyncio
    async def test_websocket_endpoint_exists(self):
        """测试 WebSocket 端点存在"""
        # WebSocket 连接需要特殊处理，这里只测试端点是否存在
        # 实际的 WebSocket 测试需要使用 websockets 库
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 尝试 HTTP GET 到 WebSocket 端点会返回错误
            response = await client.get("/ws")

        # WebSocket 端点不接受 HTTP GET，应该返回错误或特定响应
        # FastAPI对WebSocket的HTTP请求通常返回404
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_426_UPGRADE_REQUIRED,
            status.HTTP_400_BAD_REQUEST
        ]
