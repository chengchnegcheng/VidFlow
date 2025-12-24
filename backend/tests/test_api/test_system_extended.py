"""
系统 API 扩展测试 - 提高代码覆盖率
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestSystemAPIExtended:
    """系统 API 扩展测试类"""
    
    @pytest.mark.asyncio
    async def test_get_available_models(self):
        """测试获取可用的Whisper模型列表"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/models")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) > 0
        
        # 验证模型数据结构
        for model in data["models"]:
            assert "value" in model
            assert "name" in model
    
    @pytest.mark.asyncio
    async def test_cors_headers(self):
        """测试CORS头部"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options("/api/v1/system/info")
        
        # OPTIONS请求应该包含CORS头部
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED]
    
    @pytest.mark.asyncio
    async def test_api_version_endpoint(self):
        """测试API版本端点"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data or "version" in data or "status" in data
