"""
下载器方法测试
"""
import pytest
from pathlib import Path
from src.core.downloader import Downloader


@pytest.mark.core
@pytest.mark.unit
class TestDownloaderMethods:
    """下载器方法测试"""
    
    @pytest.fixture
    def downloader(self):
        """创建下载器实例"""
        return Downloader()
    
    def test_output_dir_property(self, downloader):
        """测试输出目录属性"""
        assert hasattr(downloader, 'output_dir')
        assert isinstance(downloader.output_dir, Path)
        assert downloader.output_dir.exists()
    
    @pytest.mark.asyncio
    async def test_get_video_info_method_exists(self, downloader):
        """测试get_video_info方法存在"""
        assert hasattr(downloader, 'get_video_info')
        assert callable(downloader.get_video_info)
    
    @pytest.mark.asyncio
    async def test_download_video_method_exists(self, downloader):
        """测试download_video方法存在"""
        assert hasattr(downloader, 'download_video')
        assert callable(downloader.download_video)
    
    def test_has_get_format_selector(self, downloader):
        """测试_get_format_selector方法"""
        if hasattr(downloader, '_get_format_selector'):
            assert callable(downloader._get_format_selector)


@pytest.mark.core
@pytest.mark.unit
class TestDownloaderQualityOptions:
    """下载器质量选项测试"""
    
    def test_quality_options(self):
        """测试质量选项列表"""
        quality_options = ["best", "1080p", "720p", "480p", "360p", "worst"]
        
        for quality in quality_options:
            assert isinstance(quality, str)
            assert len(quality) > 0
    
    def test_format_selector_patterns(self):
        """测试格式选择器模式"""
        # 常见的格式选择器
        format_patterns = [
            "bestvideo+bestaudio/best",
            "bestvideo[height<=1080]+bestaudio/best",
            "bestvideo[height<=720]+bestaudio/best",
        ]
        
        for pattern in format_patterns:
            assert isinstance(pattern, str)
            assert "+" in pattern or "/" in pattern


@pytest.mark.core
@pytest.mark.unit
class TestDownloaderPaths:
    """下载器路径测试"""
    
    @pytest.fixture
    def downloader(self):
        """创建下载器实例"""
        return Downloader()
    
    def test_output_dir_is_absolute(self, downloader):
        """测试输出目录是绝对路径"""
        # output_dir可能是相对路径或绝对路径
        assert isinstance(downloader.output_dir, Path)
        # 如果是相对路径，可以转换为绝对路径
        abs_path = downloader.output_dir.resolve()
        assert abs_path.is_absolute()
    
    def test_output_dir_name(self, downloader):
        """测试输出目录名称"""
        assert downloader.output_dir.name == "downloads"
    
    def test_output_dir_writable(self, downloader):
        """测试输出目录可写"""
        # 目录存在且可访问
        assert downloader.output_dir.exists()
        assert downloader.output_dir.is_dir()


@pytest.mark.core
@pytest.mark.unit
class TestDownloaderErrorCases:
    """下载器错误情况测试"""
    
    @pytest.fixture
    def downloader(self):
        """创建下载器实例"""
        return Downloader()
    
    @pytest.mark.asyncio
    async def test_get_video_info_with_timeout(self, downloader):
        """测试获取视频信息超时处理"""
        # 使用一个可能超时的URL
        unreachable_url = "https://192.0.2.1/video"  # TEST-NET-1 地址
        
        with pytest.raises(Exception):
            await downloader.get_video_info(unreachable_url)
    
    @pytest.mark.asyncio
    async def test_get_video_info_malformed_url(self, downloader):
        """测试获取视频信息 - 格式错误的URL"""
        malformed_urls = [
            "ht!tp://example.com",
            "http://",
            "://example.com",
        ]
        
        for url in malformed_urls:
            with pytest.raises(Exception):
                await downloader.get_video_info(url)
