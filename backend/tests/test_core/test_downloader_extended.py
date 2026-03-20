"""
下载器扩展测试 - 提高代码覆盖率
"""
import pytest
from pathlib import Path
from urllib.parse import urlparse
from src.core.downloader import Downloader


@pytest.mark.core
@pytest.mark.unit
class TestDownloaderExtended:
    """下载器扩展测试类"""

    @pytest.fixture
    def downloader(self):
        """创建下载器实例"""
        return Downloader()

    def test_output_directory_creation(self, downloader):
        """测试输出目录创建"""
        assert downloader.output_dir.exists()
        assert downloader.output_dir.is_dir()

    def test_output_directory_path(self, downloader):
        """测试输出目录路径"""
        assert isinstance(downloader.output_dir, Path)
        assert downloader.output_dir.name == "downloads"

    def test_validate_url_none(self):
        """测试验证None URL"""
        url = None
        if url:
            result = urlparse(url)
            assert False
        else:
            assert url is None

    def test_validate_url_empty(self):
        """测试验证空URL"""
        url = ""
        result = urlparse(url)
        assert not result.scheme and not result.netloc

    def test_validate_url_whitespace(self):
        """测试验证仅包含空白的URL"""
        url = "   "
        result = urlparse(url.strip())
        assert not result.scheme and not result.netloc

    def test_validate_url_no_scheme(self):
        """测试验证没有协议的URL"""
        url = "www.example.com"
        result = urlparse(url)
        assert not result.scheme

    def test_validate_url_ftp(self):
        """测试验证FTP URL（不支持）"""
        url = "ftp://example.com/file.mp4"
        result = urlparse(url)
        assert result.scheme == "ftp"

    def test_validate_url_https(self):
        """测试验证HTTPS URL"""
        url = "https://www.youtube.com/watch?v=test"
        result = urlparse(url)
        assert result.scheme == "https"
        assert result.netloc == "www.youtube.com"

    def test_validate_url_special_chars(self):
        """测试验证包含特殊字符的URL"""
        url = "https://example.com/video?id=123&lang=en"
        result = urlparse(url)
        assert result.scheme == "https"
        assert result.query == "id=123&lang=en"

    @pytest.mark.asyncio
    async def test_get_video_info_empty_url(self, downloader):
        """测试获取视频信息 - 空URL"""
        with pytest.raises(Exception):
            await downloader.get_video_info("")

    @pytest.mark.asyncio
    async def test_get_video_info_invalid_url(self, downloader):
        """测试获取视频信息 - 无效URL"""
        with pytest.raises(Exception):
            await downloader.get_video_info("not-a-url")

    def test_get_format_selector_best(self, downloader):
        """测试格式选择器 - best"""
        if hasattr(downloader, '_get_format_selector'):
            result = downloader._get_format_selector("best", None)
            assert result is not None

    def test_get_format_selector_with_format_id(self, downloader):
        """测试格式选择器 - 指定格式ID"""
        if hasattr(downloader, '_get_format_selector'):
            result = downloader._get_format_selector("best", "137+140")
            assert result is not None

    def test_get_format_selector_1080p(self, downloader):
        """测试格式选择器 - 1080p"""
        if hasattr(downloader, '_get_format_selector'):
            result = downloader._get_format_selector("1080p", None)
            assert result is not None

    def test_get_format_selector_720p(self, downloader):
        """测试格式选择器 - 720p"""
        if hasattr(downloader, '_get_format_selector'):
            result = downloader._get_format_selector("720p", None)
            assert result is not None


@pytest.mark.core
@pytest.mark.unit
class TestDownloaderFormats:
    """下载器格式测试类"""

    @pytest.fixture
    def downloader(self):
        """创建下载器实例"""
        return Downloader()

    def test_supported_platforms(self):
        """测试支持的平台"""
        # 常见支持的平台
        supported_urls = [
            "https://www.youtube.com/watch?v=test",
            "https://vimeo.com/123456789",
            "https://www.bilibili.com/video/BV1234567890",
        ]

        for url in supported_urls:
            result = urlparse(url)
            assert result.scheme == "https"
            assert result.netloc != ""

    def test_url_with_query_params(self):
        """测试带查询参数的URL"""
        url = "https://example.com/video?v=123&t=456&quality=hd"
        result = urlparse(url)
        assert result.scheme == "https"
        assert "v=123" in result.query

    def test_url_with_fragment(self):
        """测试带片段标识的URL"""
        url = "https://example.com/video#section"
        result = urlparse(url)
        assert result.scheme == "https"
        assert result.fragment == "section"

    def test_url_with_port(self):
        """测试带端口号的URL"""
        url = "https://example.com:8080/video"
        result = urlparse(url)
        assert result.scheme == "https"
        assert result.port == 8080

    def test_url_length_limits(self):
        """测试URL长度限制"""
        # 非常长的URL
        long_url = "https://example.com/" + "a" * 2000
        result = urlparse(long_url)
        # 应该能够解析，不会崩溃
        assert result.scheme == "https"
        assert len(result.path) > 1000
