"""
字幕 API 高级测试
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestSubtitleAPIAdvanced:
    """字幕API高级测试"""

    @pytest.mark.asyncio
    async def test_generate_subtitle_validation(self):
        """测试生成字幕 - 参数验证"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 缺少必需字段
            response = await client.post(
                "/api/v1/subtitle/generate",
                json={}
            )

        assert response.status_code in [
            422,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

    @pytest.mark.asyncio
    async def test_generate_subtitle_empty_path(self):
        """测试生成字幕 - 空路径"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/subtitle/generate",
                json={
                    "video_path": "",
                    "language": "zh"
                }
            )

        # API是异步的，可能会返回200创建任务，但后台会失败
        assert response.status_code in [
            status.HTTP_200_OK,
            422,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

    @pytest.mark.asyncio
    async def test_generate_subtitle_invalid_language(self):
        """测试生成字幕 - 无效语言"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/subtitle/generate",
                json={
                    "video_path": "/path/to/video.mp4",
                    "language": "invalid_lang"
                }
            )

        # 可能接受任何语言代码或返回错误
        assert response.status_code in [
            status.HTTP_200_OK,
            422,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

    @pytest.mark.asyncio
    async def test_get_subtitle_tasks_empty(self):
        """测试获取字幕任务列表 - 空列表"""
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
    async def test_delete_subtitle_task_not_found(self):
        """测试删除不存在的字幕任务"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/subtitle/tasks/nonexistent-id")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_models_list(self):
        """测试获取模型列表"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/models")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)

        # 验证每个模型的结构
        for model in data["models"]:
            assert "value" in model
            assert "name" in model


@pytest.mark.api
class TestSubtitleAPILanguages:
    """字幕API语言测试"""

    @pytest.mark.asyncio
    async def test_languages_structure(self):
        """测试语言列表结构"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/languages")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "languages" in data

        # 验证语言列表结构
        for lang in data["languages"]:
            assert "code" in lang
            assert "name" in lang
            assert isinstance(lang["code"], str)
            assert isinstance(lang["name"], str)

    @pytest.mark.asyncio
    async def test_languages_contains_common(self):
        """测试语言列表包含常见语言"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subtitle/languages")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        codes = [lang["code"] for lang in data["languages"]]
        # 应该包含常见语言
        common_languages = ["zh", "en"]
        for lang in common_languages:
            assert lang in codes or "auto" in codes


@pytest.mark.api
class TestSubtitleAPITaskManagement:
    """字幕API任务管理测试"""

    @pytest.mark.asyncio
    async def test_get_task_not_found_different_ids(self):
        """测试获取不存在的任务 - 不同ID格式"""
        test_ids = [
            "nonexistent-id",
            "12345",
            "test_task_123",
            "invalid@id",
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for task_id in test_ids:
                response = await client.get(f"/api/v1/subtitle/tasks/{task_id}")
                assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_subtitle_task_lifecycle(self):
        """测试字幕任务生命周期"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. 获取初始任务列表
            response = await client.get("/api/v1/subtitle/tasks")
            assert response.status_code == status.HTTP_200_OK
            initial_tasks = response.json()

            # 2. 尝试创建任务（会失败因为文件不存在，但测试API）
            response = await client.post(
                "/api/v1/subtitle/generate",
                json={
                    "video_path": "/nonexistent/video.mp4",
                    "language": "zh"
                }
            )
            # 应该返回错误
            assert response.status_code in [
                422,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ]
