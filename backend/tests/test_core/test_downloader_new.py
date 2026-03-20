"""
下载器新功能测试
测试抖音下载器、缓存管理器等新增功能
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from src.core.downloaders import (
    DownloaderFactory,
    DouyinDownloader,
    VideoInfoCache,
    get_cache,
    BaseDownloader
)


@pytest.mark.core
@pytest.mark.unit
class TestDouyinDownloader:
    """抖音下载器测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        """创建抖音下载器实例"""
        return DouyinDownloader(output_dir=str(tmp_path))

    def test_supports_url_douyin(self, downloader):
        """测试抖音URL识别"""
        douyin_urls = [
            "https://www.douyin.com/video/1234567890",
            "https://v.douyin.com/abc123/",
            "http://v.douyin.com/xyz/",
        ]

        for url in douyin_urls:
            assert DouyinDownloader.supports_url(url), f"Should support: {url}"

    def test_supports_url_tiktok(self, downloader):
        """测试TikTok URL识别"""
        tiktok_urls = [
            "https://www.tiktok.com/@user/video/1234567890",
            "https://tiktok.com/t/abc123/",
            "http://www.tiktok.com/video/xyz",
        ]

        for url in tiktok_urls:
            assert DouyinDownloader.supports_url(url), f"Should support: {url}"

    def test_supports_url_invalid(self, downloader):
        """测试不支持的URL"""
        invalid_urls = [
            "https://youtube.com/watch?v=123",
            "https://bilibili.com/video/BV123",
            "https://example.com",
            "not-a-url"
        ]

        for url in invalid_urls:
            assert not DouyinDownloader.supports_url(url), f"Should not support: {url}"

    @pytest.mark.asyncio
    async def test_resolve_short_url_passthrough(self, downloader):
        """测试完整URL直接返回"""
        full_url = "https://www.douyin.com/video/1234567890"
        resolved = await downloader._resolve_short_url(full_url)
        assert resolved == full_url

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_resolve_short_url_redirect(self, mock_client, downloader):
        """测试短链接解析"""
        short_url = "https://v.douyin.com/abc123/"
        expected_url = "https://www.douyin.com/video/1234567890"

        # Mock httpx response
        mock_response = Mock()
        mock_response.url = expected_url

        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance

        resolved = await downloader._resolve_short_url(short_url)
        assert resolved == expected_url

    def test_parse_formats(self, downloader):
        """测试格式解析"""
        formats = [
            {
                'format_id': '720p',
                'ext': 'mp4',
                'format_note': 'HD',
                'filesize': 1024000,
                'width': 1280,
                'height': 720,
                'fps': 30
            },
            {
                'format_id': '1080p',
                'ext': 'mp4',
                'filesize': None,
                'height': 1080
            }
        ]

        parsed = downloader._parse_formats(formats)

        assert len(parsed) == 2
        assert parsed[0]['format_id'] == '720p'
        assert parsed[0]['height'] == 720
        assert parsed[1]['format_id'] == '1080p'

    def test_get_format_selector(self, downloader):
        """测试格式选择器"""
        # 最佳质量
        assert 'best' in downloader._get_format_selector('best', 'mp4')

        # 仅音频
        assert 'audio' in downloader._get_format_selector('audio', 'mp4')

        # 指定分辨率
        selector = downloader._get_format_selector('720p', 'mp4')
        assert '720' in selector


@pytest.mark.core
@pytest.mark.unit
class TestVideoInfoCache:
    """视频信息缓存测试"""

    @pytest.fixture
    def cache(self, tmp_path):
        """创建缓存实例"""
        cache_dir = tmp_path / "cache"
        return VideoInfoCache(cache_dir=str(cache_dir), ttl_hours=24, max_memory_items=5)

    def test_cache_initialization(self, cache):
        """测试缓存初始化"""
        assert cache is not None
        assert cache.cache_dir.exists()
        assert cache.ttl.total_seconds() == 24 * 3600
        assert cache.max_memory_items == 5

    def test_get_cache_key(self, cache):
        """测试缓存键生成"""
        url1 = "https://example.com/video1"
        url2 = "https://example.com/video2"

        key1 = cache._get_cache_key(url1)
        key2 = cache._get_cache_key(url2)

        # 不同URL应该生成不同的键
        assert key1 != key2
        # 键应该是MD5哈希（32字符）
        assert len(key1) == 32
        assert len(key2) == 32

    def test_set_and_get_cache(self, cache):
        """测试缓存存储和读取"""
        url = "https://example.com/video1"
        info = {
            'title': 'Test Video',
            'duration': 120,
            'uploader': 'Test User'
        }

        # 存储
        cache.set(url, info)

        # 读取
        cached_info = cache.get(url)

        assert cached_info is not None
        assert cached_info['title'] == 'Test Video'
        assert cached_info['duration'] == 120

    def test_cache_miss(self, cache):
        """测试缓存未命中"""
        url = "https://example.com/nonexistent"
        cached_info = cache.get(url)
        assert cached_info is None

    def test_memory_cache_limit(self, cache):
        """测试内存缓存大小限制"""
        # 添加超过限制的条目
        for i in range(10):
            url = f"https://example.com/video{i}"
            info = {'title': f'Video {i}'}
            cache.set(url, info)

        # 内存缓存应该只保留最新的5个
        assert len(cache._memory_cache) <= cache.max_memory_items

    def test_clear_specific_cache(self, cache):
        """测试清除特定URL缓存"""
        url = "https://example.com/video1"
        info = {'title': 'Test Video'}

        cache.set(url, info)
        assert cache.get(url) is not None

        cache.clear(url)
        assert cache.get(url) is None

    def test_clear_all_cache(self, cache):
        """测试清除所有缓存"""
        # 添加多个缓存
        for i in range(3):
            url = f"https://example.com/video{i}"
            cache.set(url, {'title': f'Video {i}'})

        cache.clear()

        # 所有缓存应该被清除
        assert len(cache._memory_cache) == 0

    def test_get_stats(self, cache):
        """测试缓存统计"""
        # 添加一些缓存
        for i in range(3):
            url = f"https://example.com/video{i}"
            cache.set(url, {'title': f'Video {i}'})

        stats = cache.get_stats()

        assert 'cache_dir' in stats
        assert 'file_count' in stats
        assert 'total_size_bytes' in stats
        assert 'memory_cache_count' in stats
        assert stats['memory_cache_count'] == 3


@pytest.mark.core
@pytest.mark.unit
class TestDownloaderFactory:
    """下载器工厂测试"""

    def test_get_downloader_youtube(self):
        """测试YouTube下载器选择"""
        urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "http://youtube.com/watch?v=abc",
        ]

        for url in urls:
            downloader = DownloaderFactory.get_downloader(url)
            assert downloader.__class__.__name__ == 'YoutubeDownloader'

    def test_get_downloader_bilibili(self):
        """测试Bilibili下载器选择"""
        urls = [
            "https://www.bilibili.com/video/BV1xx411c7mD",
            "https://b23.tv/abc123",
        ]

        for url in urls:
            downloader = DownloaderFactory.get_downloader(url)
            assert downloader.__class__.__name__ == 'BilibiliDownloader'

    def test_get_downloader_douyin(self):
        """测试抖音下载器选择"""
        urls = [
            "https://www.douyin.com/video/1234567890",
            "https://v.douyin.com/abc123/",
            "https://www.tiktok.com/@user/video/123",
        ]

        for url in urls:
            downloader = DownloaderFactory.get_downloader(url)
            assert downloader.__class__.__name__ == 'DouyinDownloader'

    def test_get_downloader_generic(self):
        """测试通用下载器选择"""
        urls = [
            "https://vimeo.com/123456789",
            "https://twitter.com/user/status/123",
            "https://example.com/video",
        ]

        for url in urls:
            downloader = DownloaderFactory.get_downloader(url)
            assert downloader.__class__.__name__ == 'GenericDownloader'

    def test_detect_platform(self):
        """测试平台检测"""
        test_cases = {
            "https://www.youtube.com/watch?v=123": "youtube",
            "https://www.bilibili.com/video/BV123": "bilibili",
            "https://www.douyin.com/video/123": "douyin",
            "https://www.tiktok.com/@user/video/123": "tiktok",
            "https://twitter.com/user/status/123": "twitter",
            "https://example.com/video": "generic",
        }

        for url, expected_platform in test_cases.items():
            platform = DownloaderFactory.detect_platform(url)
            assert platform == expected_platform, f"URL: {url}, Expected: {expected_platform}, Got: {platform}"


@pytest.mark.core
@pytest.mark.unit
class TestBaseDownloader:
    """基础下载器测试"""

    def test_sanitize_filename_basic(self):
        """测试文件名清理 - 基础"""
        from src.core.downloaders.base_downloader import BaseDownloader

        # 创建一个具体实现用于测试
        class TestDownloader(BaseDownloader):
            async def get_video_info(self, url): pass
            async def download_video(self, url, **kwargs): pass
            @staticmethod
            def supports_url(url): return True

        downloader = TestDownloader()

        # 测试非法字符移除
        assert downloader._sanitize_filename('video<>:"/\\|?*') == 'video'

        # 测试空格处理
        assert downloader._sanitize_filename('  video  ') == 'video'

        # 测试正常文件名
        assert downloader._sanitize_filename('My Video 2023') == 'My Video 2023'

    def test_sanitize_filename_length(self):
        """测试文件名长度限制"""
        from src.core.downloaders.base_downloader import BaseDownloader

        class TestDownloader(BaseDownloader):
            async def get_video_info(self, url): pass
            async def download_video(self, url, **kwargs): pass
            @staticmethod
            def supports_url(url): return True

        downloader = TestDownloader()

        # 超长文件名
        long_name = "a" * 300
        sanitized = downloader._sanitize_filename(long_name)
        assert len(sanitized) <= 200

    def test_sanitize_filename_empty(self):
        """测试空文件名"""
        from src.core.downloaders.base_downloader import BaseDownloader

        class TestDownloader(BaseDownloader):
            async def get_video_info(self, url): pass
            async def download_video(self, url, **kwargs): pass
            @staticmethod
            def supports_url(url): return True

        downloader = TestDownloader()

        # 空字符串应该返回默认名称
        assert downloader._sanitize_filename('') == 'video'
        assert downloader._sanitize_filename('   ') == 'video'


@pytest.mark.integration
class TestDownloaderIntegration:
    """下载器集成测试（需要网络）"""

    @pytest.mark.skip(reason="Requires network connection")
    @pytest.mark.asyncio
    async def test_youtube_video_info(self):
        """测试YouTube视频信息获取"""
        from src.core.downloaders import YoutubeDownloader

        downloader = YoutubeDownloader()
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll

        try:
            info = await downloader.get_video_info(url)

            assert 'title' in info
            assert 'duration' in info
            assert 'thumbnail' in info
            assert info['duration'] > 0
        except Exception as e:
            pytest.skip(f"Network or API error: {e}")

    @pytest.mark.skip(reason="Requires network connection")
    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """测试缓存性能提升"""
        import time
        from src.core.downloaders import YoutubeDownloader

        downloader = YoutubeDownloader()
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        try:
            # 首次获取（无缓存）
            start = time.time()
            info1 = await downloader.get_video_info(url)
            time1 = time.time() - start

            # 第二次获取（应该使用缓存）
            start = time.time()
            info2 = await downloader.get_video_info(url)
            time2 = time.time() - start

            # 缓存应该显著提升性能
            assert time2 < time1 * 0.5  # 至少快50%
            assert info1['title'] == info2['title']
        except Exception as e:
            pytest.skip(f"Network or API error: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
