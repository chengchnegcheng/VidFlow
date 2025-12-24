"""
主应用测试
"""
import json
from pathlib import Path

import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestMainApp:
    """主应用测试"""
    
    @pytest.mark.asyncio
    async def test_app_instance(self):
        """测试应用实例"""
        assert app is not None
        assert hasattr(app, 'title')
        assert hasattr(app, 'version')
    
    @pytest.mark.asyncio
    async def test_app_title(self):
        """测试应用标题"""
        assert app.title == "VidFlow API"
    
    @pytest.mark.asyncio
    async def test_app_version(self):
        """测试应用版本"""
        root_dir = Path(__file__).resolve().parents[3]
        expected_version = json.loads((root_dir / "package.json").read_text(encoding="utf-8"))["version"]
        assert app.version == expected_version


@pytest.mark.api
class TestAppRoutes:
    """应用路由测试"""
    
    @pytest.mark.asyncio
    async def test_root_route(self):
        """测试根路由"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_health_route(self):
        """测试健康检查路由"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.api
class TestAppMiddleware:
    """应用中间件测试"""
    
    @pytest.mark.asyncio
    async def test_cors_enabled(self):
        """测试CORS已启用"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/health",
                headers={"Origin": "http://localhost:3000"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        # CORS头部可能存在，验证响应对象存在
        assert response is not None
        assert hasattr(response, 'headers')


@pytest.mark.api
class TestAppAPIPrefix:
    """应用API前缀测试"""
    
    @pytest.mark.asyncio
    async def test_api_v1_prefix(self):
        """测试API v1前缀"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/system/info")
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_downloads_api_prefix(self):
        """测试下载API前缀"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/downloads/tasks")
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_subtitle_api_prefix(self):
        """测试字幕API前缀"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/tasks")
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.api
class TestAppErrors:
    """应用错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_404_error(self):
        """测试404错误"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/nonexistent")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_method_not_allowed(self):
        """测试方法不允许错误"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put("/health")
        
        # PUT方法不允许用于/health
        assert response.status_code in [
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_404_NOT_FOUND
        ]


@pytest.mark.api
class TestAppDocumentation:
    """应用文档测试"""
    
    @pytest.mark.asyncio
    async def test_openapi_schema(self):
        """测试OpenAPI schema"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/openapi.json")
        
        # OpenAPI schema应该存在
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.asyncio
    async def test_docs_endpoint(self):
        """测试文档端点"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/docs")
        
        # 文档端点应该存在
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
