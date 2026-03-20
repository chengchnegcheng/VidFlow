"""
下载 API 扩展测试 - 提高代码覆盖率
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestDownloadsAPIExtended:
    """下载 API 扩展测试类"""

    @pytest.mark.asyncio
    async def test_get_video_info_empty_url(self):
        """测试获取视频信息 - 空URL"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={"url": ""}
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_video_info_missing_url(self):
        """测试获取视频信息 - 缺少URL参数"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={}
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_task_by_id_not_found(self):
        """测试获取不存在的任务"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/downloads/tasks/nonexistent-task-id")

        # 应该返回404或500
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

    @pytest.mark.asyncio
    async def test_pause_task_not_found(self):
        """测试暂停不存在的任务"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/downloads/tasks/nonexistent-id/pause")

        # 应该返回404或500
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

    @pytest.mark.asyncio
    async def test_resume_task_not_found(self):
        """测试恢复不存在的任务"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/downloads/tasks/nonexistent-id/resume")

        # 应该返回404或500
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self):
        """测试取消不存在的任务"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/downloads/tasks/nonexistent-id/cancel")

        # 应该返回404或500
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self):
        """测试删除不存在的任务"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/downloads/tasks/nonexistent-id")

        # 应该返回404或500
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
