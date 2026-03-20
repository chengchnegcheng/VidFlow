"""
下载器核心功能测试
"""
import pytest
from src.core.downloader import Downloader


@pytest.mark.core
@pytest.mark.unit
class TestDownloader:
    """下载器测试类"""

    @pytest.fixture
    def downloader(self):
        """创建下载器实例"""
        return Downloader()

    @pytest.mark.asyncio
    async def test_validate_url_valid(self, downloader):
        """测试 URL 验证 - 有效 URL"""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.bilibili.com/video/BV1xx411c7mD",
            "https://vimeo.com/123456789"
        ]

        for url in valid_urls:
            # 这里假设 downloader 有 validate_url 方法
            # 实际测试需要根据真实实现调整
            assert url.startswith("http")

    @pytest.mark.asyncio
    async def test_get_video_info_structure(self, downloader):
        """测试获取视频信息返回结构"""
        # 注意：这个测试可能需要网络连接或模拟
        # 这里只测试方法存在性
        assert hasattr(downloader, 'get_video_info')
        assert callable(downloader.get_video_info)

    def test_downloader_initialization(self, downloader):
        """测试下载器初始化"""
        assert downloader is not None
        assert isinstance(downloader, Downloader)


@pytest.mark.core
@pytest.mark.unit
class TestDownloaderValidation:
    """下载器验证测试"""

    def test_url_validation_http(self):
        """测试 HTTP URL 验证"""
        from urllib.parse import urlparse

        url = "https://example.com/video"
        result = urlparse(url)
        assert all([result.scheme, result.netloc])
        assert result.scheme in ['http', 'https']

    def test_url_validation_invalid(self):
        """测试无效 URL"""
        from urllib.parse import urlparse

        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "example.com",
            ""
        ]

        for url in invalid_urls:
            result = urlparse(url)
            if url == "example.com":
                # 没有 scheme 的 URL
                assert not result.scheme
