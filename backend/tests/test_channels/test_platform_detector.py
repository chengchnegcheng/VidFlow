"""
平台检测器属性测试

Property 2: URL Pattern Detection Correctness
Validates: Requirements 2.1
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
import re

from src.core.channels.platform_detector import PlatformDetector


# ============================================================================
# Strategies for generating test data
# ============================================================================

# 已知的视频号域名
KNOWN_CHANNELS_DOMAINS = [
    "finder.video.qq.com",
    "channels.weixin.qq.com",
    "findermp.video.qq.com",
    "szextshort.weixin.qq.com",
    "mpvideo.qpic.cn",
    "finder.video.wechat.com",
]

# 非视频号域名
NON_CHANNELS_DOMAINS = [
    "youtube.com",
    "bilibili.com",
    "douyin.com",
    "tiktok.com",
    "vimeo.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "weibo.com",
    "qq.com",  # 普通 QQ 域名，不是视频号
    "weixin.qq.com",  # 普通微信域名，不是视频号
    "example.com",
    "localhost",
]


@st.composite
def valid_channels_url_strategy(draw):
    """生成有效的视频号 URL"""
    domain = draw(st.sampled_from(KNOWN_CHANNELS_DOMAINS))
    path = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='/-_'),
        min_size=0,
        max_size=50
    ))

    # 对于 szextshort.weixin.qq.com，需要包含 finder
    if domain == "szextshort.weixin.qq.com":
        path = f"/finder/{path}"
    elif domain == "channels.weixin.qq.com":
        path = f"/video/{path}?encfilekey=testkey123456"

    protocol = draw(st.sampled_from(["http://", "https://"]))
    return f"{protocol}{domain}/{path}"


@st.composite
def invalid_url_strategy(draw):
    """生成非视频号 URL"""
    domain = draw(st.sampled_from(NON_CHANNELS_DOMAINS))
    path = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='/-_'),
        min_size=0,
        max_size=50
    ))
    protocol = draw(st.sampled_from(["http://", "https://"]))
    return f"{protocol}{domain}/{path}"


@st.composite
def random_url_strategy(draw):
    """生成随机 URL（可能有效也可能无效）"""
    # 使用更简单的域名生成策略，避免过多过滤
    tld = draw(st.sampled_from([".com", ".cn", ".net", ".org", ".io"]))
    domain_name = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=3,
        max_size=15
    ))

    subdomain = draw(st.one_of(
        st.just(""),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=10).map(lambda x: x + ".")
    ))

    domain = f"{subdomain}{domain_name}{tld}"

    path = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789/-_",
        min_size=0,
        max_size=50
    ))

    protocol = draw(st.sampled_from(["http://", "https://"]))
    return f"{protocol}{domain}/{path}"


# ============================================================================
# Property 2: URL Pattern Detection Correctness
# Validates: Requirements 2.1
# ============================================================================

class TestURLPatternDetection:
    """
    Property 2: URL Pattern Detection Correctness

    For any URL string, the PlatformDetector.is_channels_video_url() function
    should return true if and only if the URL matches known video号 patterns
    (finder.video.qq.com, channels.weixin.qq.com, etc.), and false for all other URLs.

    **Feature: weixin-channels-download, Property 2: URL Pattern Detection Correctness**
    **Validates: Requirements 2.1**
    """

    @given(url=valid_channels_url_strategy())
    @settings(max_examples=100)
    def test_valid_channels_urls_are_detected(self, url: str):
        """所有有效的视频号 URL 都应该被检测到"""
        result = PlatformDetector.is_channels_video_url(url)
        assert result is True, f"Expected True for valid channels URL: {url}"

    @given(url=invalid_url_strategy())
    @settings(max_examples=100)
    def test_non_channels_urls_are_rejected(self, url: str):
        """所有非视频号 URL 都应该被拒绝"""
        result = PlatformDetector.is_channels_video_url(url)
        assert result is False, f"Expected False for non-channels URL: {url}"

    @given(url=random_url_strategy())
    @settings(max_examples=100)
    def test_detection_is_deterministic(self, url: str):
        """检测结果应该是确定性的（多次调用结果相同）"""
        result1 = PlatformDetector.is_channels_video_url(url)
        result2 = PlatformDetector.is_channels_video_url(url)
        result3 = PlatformDetector.is_channels_video_url(url)

        assert result1 == result2 == result3, "Detection should be deterministic"

    def test_empty_url_returns_false(self):
        """空 URL 应该返回 False"""
        assert PlatformDetector.is_channels_video_url("") is False
        assert PlatformDetector.is_channels_video_url(None) is False

    def test_known_valid_urls(self):
        """测试已知的有效视频号 URL"""
        valid_urls = [
            "https://finder.video.qq.com/251/20304/stodownload?encfilekey=abc123",
            "https://channels.weixin.qq.com/video/abc123",
            "https://findermp.video.qq.com/video/123456",
            "https://szextshort.weixin.qq.com/finder/video/abc",
            "https://mpvideo.qpic.cn/video/abc123.mp4",
            "http://finder.video.wechat.com/video/test",
        ]

        for url in valid_urls:
            assert PlatformDetector.is_channels_video_url(url) is True, f"Should detect: {url}"

    def test_known_invalid_urls(self):
        """测试已知的无效 URL"""
        invalid_urls = [
            "https://www.youtube.com/watch?v=abc123",
            "https://www.bilibili.com/video/BV123",
            "https://www.douyin.com/video/123",
            "https://www.qq.com/",
            "https://weixin.qq.com/",
            "https://channels.weixin.qq.com/web/report-error?pf=web",
            "https://mp.weixin.qq.com/s/abc123",  # 公众号文章，不是视频号
            "ftp://finder.video.qq.com/video",  # 不同协议
        ]

        for url in invalid_urls:
            assert PlatformDetector.is_channels_video_url(url) is False, f"Should reject: {url}"

    def test_case_insensitive_detection(self):
        """URL 检测应该不区分大小写"""
        urls = [
            "https://FINDER.VIDEO.QQ.COM/video/123",
            "https://Finder.Video.QQ.Com/video/123",
            "https://finder.video.qq.com/video/123",
        ]

        for url in urls:
            assert PlatformDetector.is_channels_video_url(url) is True


# ============================================================================
# Video ID Extraction Tests
# ============================================================================

class TestVideoIdExtraction:
    """视频 ID 提取测试"""

    def test_extract_id_from_query_param(self):
        """从查询参数提取视频 ID"""
        url = "https://finder.video.qq.com/video?vid=abc123&quality=1080p"
        video_id = PlatformDetector.extract_video_id(url)
        assert video_id == "abc123"

    def test_extract_id_from_path(self):
        """从路径提取视频 ID"""
        url = "https://finder.video.qq.com/video/abcdefghij123456"
        video_id = PlatformDetector.extract_video_id(url)
        assert video_id is not None
        assert len(video_id) >= 10

    def test_extract_id_fallback_to_hash(self):
        """无法提取时使用 URL 哈希"""
        url = "https://finder.video.qq.com/v"
        video_id = PlatformDetector.extract_video_id(url)
        assert video_id is not None
        assert len(video_id) == 16  # MD5 hash truncated to 16 chars

    def test_extract_id_empty_url(self):
        """空 URL 返回 None"""
        assert PlatformDetector.extract_video_id("") is None
        assert PlatformDetector.extract_video_id(None) is None

    @given(url=valid_channels_url_strategy())
    @settings(max_examples=100)
    def test_extract_id_always_returns_value_for_valid_url(self, url: str):
        """对于有效 URL，总是能提取到 ID"""
        video_id = PlatformDetector.extract_video_id(url)
        assert video_id is not None
        assert len(video_id) > 0


# ============================================================================
# Metadata Extraction Tests
# ============================================================================

class TestMetadataExtraction:
    """元数据提取测试"""

    def test_extract_filesize_from_content_length(self):
        """从 Content-Length 提取文件大小"""
        headers = {"Content-Length": "1024000"}
        metadata = PlatformDetector.extract_metadata_from_response(
            "https://finder.video.qq.com/video.mp4",
            headers,
            b""
        )
        assert metadata is not None
        assert metadata.filesize == 1024000

    def test_extract_title_from_content_disposition(self):
        """从 Content-Disposition 提取标题"""
        headers = {"Content-Disposition": 'attachment; filename="test_video.mp4"'}
        metadata = PlatformDetector.extract_metadata_from_response(
            "https://finder.video.qq.com/video.mp4",
            headers,
            b""
        )
        assert metadata is not None
        assert metadata.title == "test_video"

    def test_extract_metadata_empty_headers(self):
        """空响应头返回空元数据"""
        metadata = PlatformDetector.extract_metadata_from_response(
            "https://finder.video.qq.com/video.mp4",
            {},
            b""
        )
        assert metadata is not None

    def test_extract_metadata_empty_url(self):
        """空 URL 返回 None"""
        metadata = PlatformDetector.extract_metadata_from_response("", {}, b"")
        assert metadata is None


# ============================================================================
# Content Type Detection Tests
# ============================================================================

class TestContentTypeDetection:
    """Content-Type 检测测试"""

    def test_video_content_types(self):
        """视频 Content-Type 应该被识别"""
        video_types = [
            "video/mp4",
            "video/webm",
            "video/x-flv",
            "application/octet-stream",
            "application/mp4",
        ]

        for ct in video_types:
            assert PlatformDetector.is_video_content_type(ct) is True

    def test_non_video_content_types(self):
        """非视频 Content-Type 应该被拒绝"""
        non_video_types = [
            "text/html",
            "application/json",
            "image/png",
            "audio/mp3",
        ]

        for ct in non_video_types:
            assert PlatformDetector.is_video_content_type(ct) is False

    def test_empty_content_type(self):
        """空 Content-Type 返回 False"""
        assert PlatformDetector.is_video_content_type("") is False
        assert PlatformDetector.is_video_content_type(None) is False


# ============================================================================
# Decryption Key Extraction Tests
# ============================================================================

class TestDecryptionKeyExtraction:
    """解密密钥提取测试"""

    def test_extract_key_from_url(self):
        """从 URL 提取数字 decodeKey"""
        url = "https://finder.video.qq.com/video?decodeKey=2065249527"
        key = PlatformDetector.extract_decryption_key(url)
        assert key == "2065249527"

    def test_extract_key_alternative_param(self):
        """从其他参数名提取数字密钥"""
        url = "https://finder.video.qq.com/video?decryptkey=1234567890"
        key = PlatformDetector.extract_decryption_key(url)
        assert key == "1234567890"

    def test_extract_key_rejects_non_numeric_value(self):
        """非数字 decodeKey 不应被接受"""
        url = "https://finder.video.qq.com/video?decryptkey=xyz789"
        key = PlatformDetector.extract_decryption_key(url)
        assert key is None

    def test_extract_key_no_key_param(self):
        """没有密钥参数返回 None"""
        url = "https://finder.video.qq.com/video?vid=123"
        key = PlatformDetector.extract_decryption_key(url)
        assert key is None

    def test_extract_key_empty_url(self):
        """空 URL 返回 None"""
        assert PlatformDetector.extract_decryption_key("") is None
        assert PlatformDetector.extract_decryption_key(None) is None
