"""
系统 API 测试
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestSystemAPI:
    """系统 API 测试类"""
    
    @pytest.mark.asyncio
    async def test_get_system_info(self):
        """测试获取系统信息"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/system/info")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # 验证返回的字段
        assert "cpu_usage" in data
        assert "memory_usage" in data
        assert "disk_usage" in data
        assert "backend_status" in data
        assert "uptime" in data
        
        # 验证数据类型
        assert isinstance(data["cpu_usage"], (int, float))
        assert isinstance(data["memory_usage"], (int, float))
        assert isinstance(data["disk_usage"], (int, float))
        assert data["backend_status"] == "online"
    
    @pytest.mark.asyncio
    async def test_check_tools_status(self):
        """测试检查工具状态"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/system/tools/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        
        # 验证工具列表结构
        for tool in data:
            assert "name" in tool
            assert "installed" in tool
            assert "required" in tool
            assert isinstance(tool["installed"], bool)
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """测试根路径"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "VidFlow API Server"
        assert data["version"] == app.version
        assert data["status"] == "running"
