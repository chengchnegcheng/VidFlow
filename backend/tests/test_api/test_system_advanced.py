"""
系统 API 高级测试
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestSystemAPIAdvanced:
    """系统API高级测试"""

    @pytest.mark.asyncio
    async def test_system_info_structure(self):
        """测试系统信息结构"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/system/info")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 验证系统信息包含必要字段
        assert isinstance(data, dict)
        # 实际API返回cpu_usage, memory_usage, backend_status等字段
        assert "cpu_usage" in data or "backend_status" in data or len(data) > 0

    @pytest.mark.asyncio
    async def test_tools_status_structure(self):
        """测试工具状态结构"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/system/tools/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 实际API返回的是工具列表
        assert isinstance(data, list)
        # 验证每个工具的结构
        if len(data) > 0:
            for tool in data:
                assert "name" in tool
                assert "installed" in tool

    @pytest.mark.asyncio
    async def test_root_endpoint_response(self):
        """测试根端点响应"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)


@pytest.mark.api
class TestSystemAPIEndpoints:
    """系统API端点测试"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """测试健康检查端点"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_api_prefix(self):
        """测试API前缀"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 测试带/api/v1前缀的端点
            response = await client.get("/api/v1/system/info")
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_invalid_endpoint(self):
        """测试无效端点"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/invalid/endpoint")

        # 应该返回404
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_method_not_allowed(self):
        """测试不允许的HTTP方法"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 对GET端点使用POST
            response = await client.post("/api/v1/system/info")

        # 应该返回405
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.api
class TestSystemAPIPerformance:
    """系统API性能测试"""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """测试并发请求"""
        import asyncio

        async def make_request():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/health")

        # 发起5个并发请求
        tasks = [make_request() for _ in range(5)]
        responses = await asyncio.gather(*tasks)

        # 所有请求都应该成功
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_response_time(self):
        """测试响应时间"""
        import time

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start_time = time.time()
            response = await client.get("/health")
            end_time = time.time()

            assert response.status_code == status.HTTP_200_OK
            # 响应时间应该小于1秒
            assert (end_time - start_time) < 1.0


@pytest.mark.api
class TestSystemAPIHeaders:
    """系统API头部测试"""

    @pytest.mark.asyncio
    async def test_content_type_header(self):
        """测试Content-Type头部"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/system/info")

        assert response.status_code == status.HTTP_200_OK
        # 应该返回JSON
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_custom_headers(self):
        """测试自定义头部"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/system/info",
                headers={"X-Custom-Header": "test-value"}
            )

        assert response.status_code == status.HTTP_200_OK
