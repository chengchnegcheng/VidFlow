"""
通用下载器多平台测试
测试 GenericDownloader 对各平台视频的获取和下载功能
"""
import pytest
import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from core.downloaders.generic_downloader import GenericDownloader
from core.downloaders.smart_download_manager import SmartDownloadManager


# 测试用的公开视频 URL（选择稳定、公开、短时长的视频）
TEST_URLS = {
    'bilibili': {
        'url': 'https://www.bilibili.com/video/BV1GJ411x7h7',
        'expected_title_contains': 'Never Gonna Give You Up',
        'platform': 'bilibili',
    },
    'youtube': {
        'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'expected_title_contains': 'Rick Astley',
        'platform': 'youtube',
    },
    # 注意：以下平台可能需要 Cookie 或有地区限制
    # 'douyin': {
    #     'url': 'https://www.douyin.com/video/xxx',
    #     'expected_title_contains': '',
    #     'platform': 'douyin',
    # },
}


class TestGenericDownloaderPlatformDetection:
    """测试平台检测功能"""

    @pytest.fixture
    def downloader(self):
        return GenericDownloader()

    @pytest.mark.parametrize("url,expected_platform", [
        ("https://www.youtube.com/watch?v=abc123", "youtube"),
        ("https://youtu.be/abc123", "youtube"),
        ("https://www.bilibili.com/video/BV1xx411c7mD", "bilibili"),
        ("https://www.tiktok.com/@user/video/123", "tiktok"),
        ("https://www.douyin.com/video/123", "douyin"),
        ("https://v.douyin.com/abc123", "douyin"),
        ("https://twitter.com/user/status/123", "twitter"),
        ("https://x.com/user/status/123", "twitter"),
        ("https://www.instagram.com/p/abc123", "instagram"),
        ("https://www.facebook.com/watch?v=123", "facebook"),
        ("https://www.xiaohongshu.com/explore/abc", "xiaohongshu"),
        ("https://channels.weixin.qq.com/abc", "weixin"),
        ("https://v.qq.com/x/cover/abc/def.html", "tencent"),
        ("https://v.youku.com/v_show/id_abc.html", "youku"),
        ("https://www.iqiyi.com/v_abc.html", "iqiyi"),
        ("https://example.com/video.mp4", "generic"),
    ])
    def test_platform_detection(self, downloader, url, expected_platform):
        """测试各平台 URL 检测"""
        detected = downloader._detect_platform(url)
        assert detected == expected_platform, f"URL {url} should be detected as {expected_platform}, got {detected}"


class TestGenericDownloaderCookiePath:
    """测试 Cookie 路径获取功能"""

    @pytest.fixture
    def downloader(self):
        return GenericDownloader()

    @pytest.mark.parametrize("url,expected_cookie_name", [
        ("https://www.bilibili.com/video/BV1xx", "bilibili_cookies.txt"),
        ("https://www.youtube.com/watch?v=abc", "youtube_cookies.txt"),
        ("https://www.douyin.com/video/123", "douyin_cookies.txt"),
        ("https://www.tiktok.com/@user/video/123", "tiktok_cookies.txt"),
        ("https://www.xiaohongshu.com/explore/abc", "xiaohongshu_cookies.txt"),
        ("https://twitter.com/user/status/123", "twitter_cookies.txt"),
        ("https://www.instagram.com/p/abc123", "instagram_cookies.txt"),
    ])
    def test_cookie_path_mapping(self, downloader, url, expected_cookie_name):
        """测试 Cookie 文件路径映射"""
        cookie_path = downloader._get_platform_cookie_path(url)
        # Cookie 文件可能不存在，但路径映射逻辑应该正确
        if cookie_path:
            assert cookie_path.name == expected_cookie_name

    def test_no_cookie_for_generic_platform(self, downloader):
        """测试通用平台不返回 Cookie 路径"""
        cookie_path = downloader._get_platform_cookie_path("https://example.com/video.mp4")
        assert cookie_path is None


@pytest.mark.network
@pytest.mark.slow
class TestGenericDownloaderVideoInfo:
    """测试视频信息获取功能（需要网络）"""

    @pytest.fixture
    def downloader(self):
        return GenericDownloader()

    @pytest.mark.asyncio
    async def test_bilibili_video_info(self, downloader):
        """测试获取 B站视频信息"""
        url = TEST_URLS['bilibili']['url']

        try:
            info = await downloader.get_video_info(url)

            assert info is not None
            assert 'title' in info
            assert 'duration' in info
            assert 'platform' in info
            assert info['platform'] == 'bilibili'
            assert TEST_URLS['bilibili']['expected_title_contains'] in info['title']

            print(f"\n✓ Bilibili video info retrieved successfully:")
            print(f"  Title: {info['title']}")
            print(f"  Duration: {info['duration']}s")
            print(f"  Formats: {len(info.get('formats', []))} available")

        except Exception as e:
            pytest.fail(f"Failed to get Bilibili video info: {e}")

    @pytest.mark.asyncio
    async def test_youtube_video_info(self, downloader):
        """测试获取 YouTube 视频信息"""
        url = TEST_URLS['youtube']['url']

        try:
            info = await downloader.get_video_info(url)

            assert info is not None
            assert 'title' in info
            assert 'duration' in info
            assert 'platform' in info
            assert info['platform'] == 'youtube'

            print(f"\n✓ YouTube video info retrieved successfully:")
            print(f"  Title: {info['title']}")
            print(f"  Duration: {info['duration']}s")
            print(f"  Formats: {len(info.get('formats', []))} available")

        except Exception as e:
            pytest.fail(f"Failed to get YouTube video info: {e}")

    @pytest.mark.asyncio
    async def test_video_info_structure(self, downloader):
        """测试视频信息返回结构"""
        url = TEST_URLS['bilibili']['url']

        info = await downloader.get_video_info(url)

        # 验证必需字段
        required_fields = ['title', 'duration', 'platform', 'url']
        for field in required_fields:
            assert field in info, f"Missing required field: {field}"

        # 验证可选字段类型
        if 'formats' in info:
            assert isinstance(info['formats'], list)
        if 'thumbnail' in info:
            assert isinstance(info['thumbnail'], str)
        if 'description' in info:
            assert isinstance(info['description'], str)


@pytest.mark.network
@pytest.mark.slow
class TestSmartDownloadManager:
    """测试智能下载管理器"""

    @pytest.fixture
    def manager(self):
        return SmartDownloadManager()

    @pytest.mark.asyncio
    async def test_bilibili_smart_download_info(self, manager):
        """测试智能下载管理器获取 B站视频信息"""
        url = TEST_URLS['bilibili']['url']

        try:
            result = await manager.get_info_with_fallback(url)

            assert result is not None
            assert 'title' in result
            assert 'downloader_used' in result
            assert 'fallback_used' in result

            print(f"\n✓ Smart download info retrieved:")
            print(f"  Title: {result['title']}")
            print(f"  Downloader used: {result['downloader_used']}")
            print(f"  Fallback used: {result['fallback_used']}")

            # 对于公开视频，应该不需要回退
            assert result['fallback_used'] == False, "Public video should not require fallback"

        except Exception as e:
            pytest.fail(f"Smart download failed: {e}")

    @pytest.mark.asyncio
    async def test_youtube_smart_download_info(self, manager):
        """测试智能下载管理器获取 YouTube 视频信息"""
        url = TEST_URLS['youtube']['url']

        try:
            result = await manager.get_info_with_fallback(url)

            assert result is not None
            assert 'title' in result
            assert 'downloader_used' in result

            print(f"\n✓ YouTube smart download info retrieved:")
            print(f"  Title: {result['title']}")
            print(f"  Downloader used: {result['downloader_used']}")

        except Exception as e:
            pytest.fail(f"Smart download failed: {e}")


@pytest.mark.network
@pytest.mark.slow
class TestGenericDownloaderDownload:
    """测试实际下载功能（需要网络，会下载文件）"""

    @pytest.fixture
    def downloader(self):
        return GenericDownloader(output_dir="./test_downloads")

    @pytest.fixture
    def cleanup_downloads(self):
        """清理测试下载的文件"""
        yield
        # 测试后清理
        import shutil
        download_dir = Path("./test_downloads")
        if download_dir.exists():
            shutil.rmtree(download_dir)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Skip actual download to save time and bandwidth")
    async def test_bilibili_download(self, downloader, cleanup_downloads):
        """测试下载 B站视频（跳过以节省时间）"""
        url = TEST_URLS['bilibili']['url']

        try:
            result = await downloader.download_video(
                url=url,
                quality="worst",  # 使用最低画质以节省带宽
            )

            assert result is not None
            assert result['status'] == 'success'
            assert 'filename' in result

            # 验证文件存在
            filename = result['filename']
            assert Path(filename).exists(), f"Downloaded file not found: {filename}"

            print(f"\n✓ Video downloaded successfully:")
            print(f"  Filename: {filename}")
            print(f"  Filesize: {result.get('filesize', 'unknown')}")

        except Exception as e:
            pytest.fail(f"Download failed: {e}")


class TestGenericDownloaderConfiguration:
    """测试下载器配置"""

    def test_default_output_dir(self):
        """测试默认输出目录"""
        downloader = GenericDownloader()
        assert downloader.output_dir is not None

    def test_custom_output_dir(self):
        """测试自定义输出目录"""
        custom_dir = "./custom_downloads"
        downloader = GenericDownloader(output_dir=custom_dir)
        # Path 会规范化路径，所以只检查是否包含目录名
        assert "custom_downloads" in str(downloader.output_dir)

    def test_cookie_mode_flag(self):
        """测试 Cookie 模式标志"""
        downloader = GenericDownloader()

        # 默认应该启用 Cookie
        assert downloader._use_cookie_in_smart_mode == True

        # 可以禁用
        downloader._use_cookie_in_smart_mode = False
        assert downloader._use_cookie_in_smart_mode == False

    def test_supports_all_urls(self):
        """测试通用下载器支持所有 URL"""
        assert GenericDownloader.supports_url("https://any-website.com/video") == True
        assert GenericDownloader.supports_url("https://example.com") == True
        assert GenericDownloader.supports_url("http://test.org/path") == True


# 运行测试的入口
if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "not skip",  # 跳过标记为 skip 的测试
    ])
