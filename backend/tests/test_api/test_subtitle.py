"""
字幕 API 测试
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestSubtitleAPI:
    """字幕 API 测试类"""
    
    @pytest.mark.asyncio
    async def test_get_subtitle_tasks(self):
        """测试获取字幕任务列表"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/tasks")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # API返回包含status、tasks、total的字典
        assert isinstance(data, dict)
        assert "status" in data
        assert "tasks" in data
        assert isinstance(data["tasks"], list)
    
    @pytest.mark.asyncio
    async def test_generate_subtitle_missing_file(self):
        """测试生成字幕 - 文件不存在"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/subtitle/generate",
                json={
                    "video_path": "/nonexistent/video.mp4",
                    "language": "zh",
                    "model_size": "base"
                }
            )
        
        # 应该返回错误（文件不存在）
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
    
    @pytest.mark.asyncio
    async def test_get_subtitle_task_not_found(self):
        """测试获取不存在的字幕任务"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/tasks/nonexistent-id")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_supported_languages(self):
        """测试获取支持的语言列表"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/languages")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # API返回的是字典格式 {'languages': [...]}
        assert isinstance(data, dict)
        assert 'languages' in data
        assert isinstance(data['languages'], list)
        # 应该包含常见语言
        assert len(data['languages']) > 0
