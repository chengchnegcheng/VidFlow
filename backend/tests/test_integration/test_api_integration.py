"""
API 集成测试
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.integration
class TestAPIIntegration:
    """API集成测试"""

    @pytest.mark.asyncio
    async def test_health_and_system_info(self):
        """测试健康检查和系统信息的集成"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 检查健康状态
            health_response = await client.get("/health")
            assert health_response.status_code == status.HTTP_200_OK

            # 获取系统信息
            system_response = await client.get("/api/v1/system/info")
            assert system_response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_api_endpoints_accessible(self):
        """测试所有主要API端点可访问"""
        endpoints = [
            "/",
            "/health",
            "/api/v1/system/info",
            "/api/v1/system/tools/status",
            "/api/v1/downloads/tasks",
            "/api/v1/subtitle/tasks",
            "/api/v1/subtitle/languages",
            "/api/v1/subtitle/models",
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for endpoint in endpoints:
                response = await client.get(endpoint)
                assert response.status_code == status.HTTP_200_OK, f"Endpoint {endpoint} failed"

    @pytest.mark.asyncio
    async def test_cors_preflight(self):
        """测试CORS预检请求"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options(
                "/api/v1/system/info",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET"
                }
            )
            # OPTIONS请求可能返回200或405
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED]


@pytest.mark.integration
class TestAPIErrorHandling:
    """API错误处理集成测试"""

    @pytest.mark.asyncio
    async def test_404_handling(self):
        """测试404错误处理"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/nonexistent/endpoint")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_invalid_json_handling(self):
        """测试无效JSON处理"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                content="invalid json",
                headers={"Content-Type": "application/json"}
            )

        # 应该返回422或400
        assert response.status_code in [422, status.HTTP_400_BAD_REQUEST]


@pytest.mark.integration
class TestAPIDataFlow:
    """API数据流集成测试"""

    @pytest.mark.asyncio
    async def test_download_task_list_structure(self):
        """测试下载任务列表数据结构"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/downloads/tasks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 验证返回结构
        assert "status" in data
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)
        assert isinstance(data["total"], int)

    @pytest.mark.asyncio
    async def test_subtitle_tasks_list_structure(self):
        """测试字幕任务列表数据结构"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/tasks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 应该返回包含status、tasks、total的字典
        assert isinstance(data, dict)
        assert "status" in data
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)
        assert isinstance(data["total"], int)

    @pytest.mark.asyncio
    async def test_languages_data_structure(self):
        """测试语言数据结构"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/languages")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "languages" in data
        assert isinstance(data["languages"], list)

        if len(data["languages"]) > 0:
            lang = data["languages"][0]
            assert "code" in lang
            assert "name" in lang

    @pytest.mark.asyncio
    async def test_models_data_structure(self):
        """测试模型数据结构"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/models")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "models" in data
        assert isinstance(data["models"], list)

        if len(data["models"]) > 0:
            model = data["models"][0]
            assert "value" in model
            assert "name" in model
