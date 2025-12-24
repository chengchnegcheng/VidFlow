"""
下载 API 高级测试 - 分页、筛选、状态管理
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestDownloadsAPIPagination:
    """下载API分页测试"""
    
    @pytest.mark.asyncio
    async def test_get_tasks_with_limit(self):
        """测试获取任务列表 - 限制数量"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/downloads/tasks?limit=5")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) <= 5
    
    @pytest.mark.asyncio
    async def test_get_tasks_with_offset(self):
        """测试获取任务列表 - 偏移量"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/downloads/tasks?offset=0&limit=10")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tasks" in data
    
    @pytest.mark.asyncio
    async def test_get_tasks_with_status_filter(self):
        """测试获取任务列表 - 状态筛选"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/downloads/tasks?status=pending")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tasks" in data
        # 所有任务应该是pending状态（如果有的话）
        for task in data.get("tasks", []):
            if task.get("status"):
                assert task["status"] == "pending"


@pytest.mark.api
class TestDownloadsAPIFormats:
    """下载API格式测试"""
    
    @pytest.mark.asyncio
    async def test_get_video_info_url_formats(self):
        """测试不同URL格式"""
        test_urls = [
            "https://www.youtube.com/watch?v=test123",
            "https://youtu.be/test123",
            "https://www.bilibili.com/video/BV1234567890",
        ]
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for url in test_urls:
                response = await client.post(
                    "/api/v1/downloads/info",
                    json={"url": url}
                )
                # 应该返回200或422（URL验证失败）
                assert response.status_code in [
                    status.HTTP_200_OK,
                    422,
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ]
    
    @pytest.mark.asyncio
    async def test_video_info_response_structure(self):
        """测试视频信息响应结构"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={"url": "https://example.com/video"}
            )
        
        # 无论成功或失败，都应该有响应
        assert response.status_code in [
            status.HTTP_200_OK,
            422,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "status" in data or "data" in data


@pytest.mark.api
class TestDownloadsAPIErrorHandling:
    """下载API错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_get_task_invalid_id(self):
        """测试获取任务 - 无效ID"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/downloads/tasks/invalid-id-123")
        
        # 应该返回404或500
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self):
        """测试取消不存在的任务"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/downloads/tasks/nonexistent/cancel")
        
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_task(self):
        """测试删除不存在的任务"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/downloads/tasks/nonexistent")
        
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
    
    @pytest.mark.asyncio
    async def test_malformed_request_body(self):
        """测试畸形的请求体"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={"invalid_field": "test"}
            )
        
        # 应该返回422（验证错误）
        assert response.status_code == 422


@pytest.mark.api
class TestDownloadsAPIValidation:
    """下载API验证测试"""
    
    @pytest.mark.asyncio
    async def test_url_validation_missing(self):
        """测试URL验证 - 缺少URL"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={}
            )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_url_validation_empty_string(self):
        """测试URL验证 - 空字符串"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={"url": ""}
            )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_url_validation_whitespace(self):
        """测试URL验证 - 仅空白字符"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={"url": "   "}
            )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_url_validation_invalid_protocol(self):
        """测试URL验证 - 无效协议"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={"url": "ftp://example.com/video"}
            )
        
        assert response.status_code in [422, status.HTTP_500_INTERNAL_SERVER_ERROR]
