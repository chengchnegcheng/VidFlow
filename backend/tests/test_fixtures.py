"""
测试fixture功能
"""
import pytest


@pytest.mark.unit
class TestFixtures:
    """测试fixture"""
    
    def test_mock_video_info_fixture(self, mock_video_info):
        """测试mock_video_info fixture"""
        assert mock_video_info is not None
        assert isinstance(mock_video_info, dict)
        assert "title" in mock_video_info
        assert "url" in mock_video_info
    
    def test_sample_download_task_fixture(self, sample_download_task):
        """测试sample_download_task fixture"""
        assert sample_download_task is not None
        assert isinstance(sample_download_task, dict)
        assert "url" in sample_download_task
    
    def test_mock_video_info_structure(self, mock_video_info):
        """测试mock视频信息结构"""
        required_fields = ["title", "url", "platform", "duration"]
        for field in required_fields:
            assert field in mock_video_info
    
    def test_sample_download_task_structure(self, sample_download_task):
        """测试示例下载任务结构"""
        required_fields = ["url", "quality"]
        for field in required_fields:
            assert field in sample_download_task


@pytest.mark.unit
class TestPytestMarkers:
    """测试pytest标记"""
    
    def test_unit_marker(self):
        """测试unit标记"""
        # 这个测试本身使用了unit标记
        assert True
    
    @pytest.mark.api
    def test_api_marker(self):
        """测试api标记"""
        assert True
    
    @pytest.mark.core
    def test_core_marker(self):
        """测试core标记"""
        assert True
    
    @pytest.mark.integration
    def test_integration_marker(self):
        """测试integration标记"""
        assert True


@pytest.mark.unit
class TestAsyncio:
    """测试asyncio支持"""
    
    @pytest.mark.asyncio
    async def test_asyncio_works(self):
        """测试asyncio正常工作"""
        import asyncio
        await asyncio.sleep(0.001)
        assert True
    
    @pytest.mark.asyncio
    async def test_async_function(self):
        """测试异步函数"""
        async def dummy_async():
            return "test"
        
        result = await dummy_async()
        assert result == "test"
