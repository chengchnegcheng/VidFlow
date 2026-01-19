"""
视频URL提取器属性测试

Property 8: Video URL Pattern Matching
Property 9: Video Deduplication by ID
Validates: Requirements 6.1, 6.4, 6.5
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock
from typing import List
from datetime import datetime, timedelta

from src.core.channels.video_url_extractor import VideoURLExtractor, ExtractedVideo


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def video_domain_strategy(draw):
    """生成视频域名"""
    domains = [
        "wxapp.tc.qq.com",
        "finder.video.qq.com",
        "findermp.video.qq.com",
        "findervideodownload.video.qq.com",
        "channels.weixin.qq.com",
        "szextshort.weixin.qq.com",
        "szvideo.weixin.qq.com",
        "vd.video.qq.com",
        "vd1.video.qq.com",
        "vd2.video.qq.com",
        "mpvideo.qpic.cn",
    ]
    return draw(st.sampled_from(domains))


@st.composite
def non_video_domain_strategy(draw):
    """生成非视频域名"""
    domains = [
        "www.google.com",
        "api.weixin.qq.com",
        "res.wx.qq.com",
        "static.example.com",
        "cdn.example.org",
        "images.qq.com",
    ]
    return draw(st.sampled_from(domains))


@st.composite
def video_url_strategy(draw):
    """生成视频URL"""
    domain = draw(video_domain_strategy())
    path_options = [
        "/stodownload?m=abc123&e=1234567890",
        "/video/abc123.mp4",
        "/finder/video123.mp4?encfilekey=xyz789",
        "/vod/abc.m3u8",
    ]
    path = draw(st.sampled_from(path_options))
    return f"https://{domain}{path}"


@st.composite
def excluded_url_strategy(draw):
    """生成应排除的URL"""
    domain = draw(video_domain_strategy())
    excluded_paths = [
        "/image.jpg",
        "/photo.png",
        "/icon.gif",
        "/cgi-bin/api",
        "/api/v1/data",
        "/script.js",
        "/style.css",
        "/beacon/track",
        "/report/log",
        "/thumbnail/small.jpg",
    ]
    path = draw(st.sampled_from(excluded_paths))
    return f"https://{domain}{path}"


@st.composite
def video_id_strategy(draw):
    """生成视频ID"""
    length = draw(st.integers(min_value=16, max_value=32))
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    return "".join(draw(st.sampled_from(chars)) for _ in range(length))


@st.composite
def extracted_video_strategy(draw):
    """生成ExtractedVideo对象"""
    video_id = draw(video_id_strategy())
    domain = draw(video_domain_strategy())
    return ExtractedVideo(
        url=f"https://{domain}/video/{video_id}.mp4",
        video_id=video_id,
        source=draw(st.sampled_from(["http", "sni", "clash_api", "ip"])),
        domain=domain,
        is_encrypted=draw(st.booleans()),
    )


@st.composite
def video_list_strategy(draw):
    """生成视频列表（可能有重复ID）"""
    num_videos = draw(st.integers(min_value=0, max_value=20))
    
    # 生成一些唯一ID
    unique_ids = [draw(video_id_strategy()) for _ in range(max(1, num_videos // 2))]
    
    videos = []
    for i in range(num_videos):
        # 有50%概率使用已有ID（制造重复）
        if unique_ids and draw(st.booleans()):
            video_id = draw(st.sampled_from(unique_ids))
        else:
            video_id = draw(video_id_strategy())
            unique_ids.append(video_id)
        
        domain = draw(video_domain_strategy())
        videos.append(ExtractedVideo(
            url=f"https://{domain}/video/{video_id}.mp4?t={i}",
            video_id=video_id,
            source="http",
            domain=domain,
        ))
    
    return videos


# ============================================================================
# Property 8: Video URL Pattern Matching
# Validates: Requirements 6.1, 6.4
# ============================================================================

class TestVideoURLPatternMatching:
    """
    Property 8: Video URL Pattern Matching
    
    For any URL string, the VideoURLExtractor.is_video_url() should return true
    if and only if the URL matches known video号 patterns AND does not match
    exclusion patterns (thumbnails, API calls, etc.).
    
    **Feature: weixin-channels-deep-research, Property 8: Video URL Pattern Matching**
    **Validates: Requirements 6.1, 6.4**
    """

    @given(url=video_url_strategy())
    @settings(max_examples=100)
    def test_video_urls_detected(self, url):
        """测试视频URL被正确检测
        
        Property: 所有匹配视频模式的URL应该被检测为视频URL。
        """
        extractor = VideoURLExtractor()
        result = extractor.is_video_url(url)
        assert result is True, f"Video URL should be detected: {url}"

    @given(url=excluded_url_strategy())
    @settings(max_examples=100)
    def test_excluded_urls_rejected(self, url):
        """测试排除URL被正确拒绝
        
        Property: 所有匹配排除模式的URL应该被拒绝。
        """
        extractor = VideoURLExtractor()
        result = extractor.is_video_url(url)
        assert result is False, f"Excluded URL should be rejected: {url}"

    @given(domain=non_video_domain_strategy())
    @settings(max_examples=100)
    def test_non_video_domains_rejected(self, domain):
        """测试非视频域名被拒绝
        
        Property: 非视频域名的URL应该被拒绝。
        """
        extractor = VideoURLExtractor()
        url = f"https://{domain}/video.mp4"
        result = extractor.is_video_url(url)
        assert result is False, f"Non-video domain should be rejected: {url}"

    def test_empty_url_rejected(self):
        """测试空URL被拒绝"""
        extractor = VideoURLExtractor()
        assert extractor.is_video_url("") is False
        assert extractor.is_video_url(None) is False

    def test_known_video_patterns(self):
        """测试已知视频模式"""
        extractor = VideoURLExtractor()
        
        video_urls = [
            "https://wxapp.tc.qq.com/stodownload?m=abc123",
            "https://finder.video.qq.com/video.mp4",
            "https://findermp.video.qq.com/abc.mp4",
            "https://channels.weixin.qq.com/video/123",
            "https://vd1.video.qq.com/video.mp4",
            "https://abc.tc.qq.com/path?encfilekey=xyz",
            "https://mpvideo.qpic.cn/video.mp4",
        ]
        
        for url in video_urls:
            assert extractor.is_video_url(url) is True, f"Should detect: {url}"

    def test_known_exclude_patterns(self):
        """测试已知排除模式"""
        extractor = VideoURLExtractor()
        
        excluded_urls = [
            "https://finder.video.qq.com/image.jpg",
            "https://finder.video.qq.com/photo.png",
            "https://finder.video.qq.com/cgi-bin/api",
            "https://finder.video.qq.com/api/data",
            "https://finder.video.qq.com/script.js",
            "https://finder.video.qq.com/beacon/track",
            "https://finder.video.qq.com/thumbnail/small.jpg",
        ]
        
        for url in excluded_urls:
            assert extractor.is_video_url(url) is False, f"Should exclude: {url}"


# ============================================================================
# Property 9: Video Deduplication by ID
# Validates: Requirements 6.5
# ============================================================================

class TestVideoDeduplicationByID:
    """
    Property 9: Video Deduplication by ID
    
    For any sequence of detected videos, the deduplicate() function should return
    a list where no two videos have the same video_id. The first occurrence of
    each video_id should be preserved.
    
    **Feature: weixin-channels-deep-research, Property 9: Video Deduplication by ID**
    **Validates: Requirements 6.5**
    """

    @given(videos=video_list_strategy())
    @settings(max_examples=100)
    def test_no_duplicate_ids_after_dedup(self, videos):
        """测试去重后没有重复ID
        
        Property: 去重后的列表中不应有两个视频具有相同的video_id。
        """
        extractor = VideoURLExtractor()
        result = extractor.deduplicate(videos)
        
        # 检查没有重复ID
        seen_ids = set()
        for video in result:
            assert video.video_id not in seen_ids, \
                f"Duplicate video_id found: {video.video_id}"
            seen_ids.add(video.video_id)

    @given(videos=video_list_strategy())
    @settings(max_examples=100)
    def test_first_occurrence_preserved(self, videos):
        """测试保留第一次出现
        
        Property: 每个video_id的第一次出现应该被保留。
        """
        extractor = VideoURLExtractor()
        result = extractor.deduplicate(videos)
        
        # 构建原始列表中每个ID的第一次出现
        first_occurrences = {}
        for video in videos:
            if video.video_id not in first_occurrences:
                first_occurrences[video.video_id] = video
        
        # 验证结果中的每个视频都是第一次出现
        for video in result:
            expected = first_occurrences[video.video_id]
            assert video.url == expected.url, \
                f"First occurrence not preserved for {video.video_id}"

    @given(videos=video_list_strategy())
    @settings(max_examples=100)
    def test_dedup_preserves_order(self, videos):
        """测试去重保持顺序
        
        Property: 去重后的列表应该保持原始顺序。
        """
        extractor = VideoURLExtractor()
        result = extractor.deduplicate(videos)
        
        # 获取原始列表中每个唯一ID的首次出现索引
        first_indices = {}
        for i, video in enumerate(videos):
            if video.video_id not in first_indices:
                first_indices[video.video_id] = i
        
        # 验证结果顺序
        prev_index = -1
        for video in result:
            current_index = first_indices[video.video_id]
            assert current_index > prev_index, \
                "Order not preserved after deduplication"
            prev_index = current_index

    def test_empty_list_dedup(self):
        """测试空列表去重"""
        extractor = VideoURLExtractor()
        result = extractor.deduplicate([])
        assert result == []

    def test_single_video_dedup(self):
        """测试单个视频去重"""
        extractor = VideoURLExtractor()
        video = ExtractedVideo(
            url="https://example.com/video.mp4",
            video_id="abc123",
            source="http",
            domain="example.com",
        )
        result = extractor.deduplicate([video])
        assert len(result) == 1
        assert result[0].video_id == "abc123"

    def test_all_unique_dedup(self):
        """测试全部唯一时去重"""
        extractor = VideoURLExtractor()
        videos = [
            ExtractedVideo(url=f"https://example.com/{i}.mp4", video_id=f"id{i}", 
                          source="http", domain="example.com")
            for i in range(5)
        ]
        result = extractor.deduplicate(videos)
        assert len(result) == 5

    def test_all_duplicate_dedup(self):
        """测试全部重复时去重"""
        extractor = VideoURLExtractor()
        videos = [
            ExtractedVideo(url=f"https://example.com/video.mp4?t={i}", video_id="same_id",
                          source="http", domain="example.com")
            for i in range(5)
        ]
        result = extractor.deduplicate(videos)
        assert len(result) == 1
        assert result[0].url == "https://example.com/video.mp4?t=0"


# ============================================================================
# Additional Unit Tests
# ============================================================================

class TestVideoIDExtraction:
    """视频ID提取测试"""

    def test_extract_encfilekey(self):
        """测试提取encfilekey"""
        extractor = VideoURLExtractor()
        url = "https://example.com/video?encfilekey=abc123xyz"
        video_id = extractor.extract_video_id(url)
        assert video_id == "abc123xyz"

    def test_extract_filekey(self):
        """测试提取filekey"""
        extractor = VideoURLExtractor()
        url = "https://example.com/video?filekey=def456"
        video_id = extractor.extract_video_id(url)
        assert video_id == "def456"

    def test_extract_vid(self):
        """测试提取vid"""
        extractor = VideoURLExtractor()
        url = "https://example.com/video?vid=ghi789"
        video_id = extractor.extract_video_id(url)
        assert video_id == "ghi789"

    def test_extract_from_path(self):
        """测试从路径提取ID"""
        extractor = VideoURLExtractor()
        url = "https://example.com/12345678901234567890123456789012.mp4"
        video_id = extractor.extract_video_id(url)
        assert video_id == "12345678901234567890123456789012"

    def test_fallback_to_hash(self):
        """测试回退到哈希"""
        extractor = VideoURLExtractor()
        url = "https://example.com/video.mp4"
        video_id = extractor.extract_video_id(url)
        assert video_id is not None
        assert len(video_id) == 16  # MD5哈希的前16位

    def test_empty_url_returns_none(self):
        """测试空URL返回None"""
        extractor = VideoURLExtractor()
        assert extractor.extract_video_id("") is None
        assert extractor.extract_video_id(None) is None


class TestExpirationCheck:
    """过期检查测试"""

    def test_not_expired(self):
        """测试未过期"""
        extractor = VideoURLExtractor()
        video = ExtractedVideo(
            url="https://example.com/video.mp4",
            video_id="abc123",
            source="http",
            domain="example.com",
            expires_at=datetime.now() + timedelta(hours=1),
        )
        assert extractor.check_expiration(video) is False

    def test_expired(self):
        """测试已过期"""
        extractor = VideoURLExtractor()
        video = ExtractedVideo(
            url="https://example.com/video.mp4",
            video_id="abc123",
            source="http",
            domain="example.com",
            expires_at=datetime.now() - timedelta(hours=1),
        )
        assert extractor.check_expiration(video) is True

    def test_no_expiration(self):
        """测试无过期时间"""
        extractor = VideoURLExtractor()
        video = ExtractedVideo(
            url="https://example.com/video.mp4",
            video_id="abc123",
            source="http",
            domain="example.com",
            expires_at=None,
        )
        assert extractor.check_expiration(video) is False


class TestExtractFromHTTP:
    """HTTP提取测试"""

    def test_extract_video_url_from_http(self):
        """测试从HTTP提取视频URL"""
        extractor = VideoURLExtractor()
        payload = b'GET https://finder.video.qq.com/video.mp4 HTTP/1.1\r\n'
        result = extractor.extract_from_http(payload)
        assert result is not None
        assert "finder.video.qq.com" in result.url

    def test_no_video_in_http(self):
        """测试HTTP中无视频"""
        extractor = VideoURLExtractor()
        payload = b'GET https://www.google.com/ HTTP/1.1\r\n'
        result = extractor.extract_from_http(payload)
        assert result is None

    def test_empty_payload(self):
        """测试空payload"""
        extractor = VideoURLExtractor()
        assert extractor.extract_from_http(b'') is None
        assert extractor.extract_from_http(None) is None


class TestExtractFromSNI:
    """SNI提取测试"""

    def test_extract_from_video_sni(self):
        """测试从视频SNI提取"""
        extractor = VideoURLExtractor()
        result = extractor.extract_from_sni("finder.video.qq.com", "1.2.3.4")
        assert result is not None
        assert result.source == "sni"
        assert result.domain == "finder.video.qq.com"

    def test_non_video_sni(self):
        """测试非视频SNI"""
        extractor = VideoURLExtractor()
        result = extractor.extract_from_sni("www.google.com", "1.2.3.4")
        assert result is None

    def test_empty_sni(self):
        """测试空SNI"""
        extractor = VideoURLExtractor()
        assert extractor.extract_from_sni("", "1.2.3.4") is None
        assert extractor.extract_from_sni(None, "1.2.3.4") is None


class TestExtractFromClashConnection:
    """Clash连接提取测试"""

    def test_extract_from_clash_connection(self):
        """测试从Clash连接提取"""
        extractor = VideoURLExtractor()
        
        conn = Mock()
        conn.host = "finder.video.qq.com"
        conn.dst_ip = "1.2.3.4"
        conn.dst_port = 443
        
        result = extractor.extract_from_clash_connection(conn)
        assert result is not None
        assert result.source == "clash_api"

    def test_non_video_clash_connection(self):
        """测试非视频Clash连接"""
        extractor = VideoURLExtractor()
        
        conn = Mock()
        conn.host = "www.google.com"
        conn.dst_ip = "1.2.3.4"
        conn.dst_port = 443
        
        result = extractor.extract_from_clash_connection(conn)
        assert result is None

    def test_empty_clash_connection(self):
        """测试空Clash连接"""
        extractor = VideoURLExtractor()
        assert extractor.extract_from_clash_connection(None) is None


class TestExtractAndDeduplicate:
    """提取并去重测试"""

    def test_extract_new_video(self):
        """测试提取新视频"""
        extractor = VideoURLExtractor()
        url = "https://finder.video.qq.com/video.mp4"
        result = extractor.extract_and_deduplicate(url)
        assert result is not None
        assert extractor.get_extracted_count() == 1

    def test_reject_duplicate(self):
        """测试拒绝重复"""
        extractor = VideoURLExtractor()
        url = "https://finder.video.qq.com/video.mp4"
        
        result1 = extractor.extract_and_deduplicate(url)
        assert result1 is not None
        
        result2 = extractor.extract_and_deduplicate(url)
        assert result2 is None
        
        assert extractor.get_extracted_count() == 1

    def test_clear_extracted_ids(self):
        """测试清除已提取ID"""
        extractor = VideoURLExtractor()
        url = "https://finder.video.qq.com/video.mp4"
        
        extractor.extract_and_deduplicate(url)
        assert extractor.get_extracted_count() == 1
        
        extractor.clear_extracted_ids()
        assert extractor.get_extracted_count() == 0
        
        # 现在可以再次提取
        result = extractor.extract_and_deduplicate(url)
        assert result is not None


class TestExtractedVideoDataclass:
    """ExtractedVideo数据类测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        video = ExtractedVideo(
            url="https://example.com/video.mp4",
            video_id="abc123",
            source="http",
            domain="example.com",
            is_encrypted=True,
            decryption_key="key123",
            quality="1080p",
        )
        
        d = video.to_dict()
        assert d["url"] == "https://example.com/video.mp4"
        assert d["video_id"] == "abc123"
        assert d["source"] == "http"
        assert d["domain"] == "example.com"
        assert d["is_encrypted"] is True
        assert d["decryption_key"] == "key123"
        assert d["quality"] == "1080p"
        assert "detected_at" in d


class TestQualityExtraction:
    """质量提取测试"""

    def test_extract_1080p(self):
        """测试提取1080p"""
        extractor = VideoURLExtractor()
        video = extractor._create_extracted_video(
            "https://example.com/video_1080p.mp4", "http"
        )
        assert video.quality == "1080p"

    def test_extract_720p(self):
        """测试提取720p"""
        extractor = VideoURLExtractor()
        video = extractor._create_extracted_video(
            "https://example.com/video_720P.mp4", "http"
        )
        assert video.quality == "720p"

    def test_extract_4k(self):
        """测试提取4K"""
        extractor = VideoURLExtractor()
        video = extractor._create_extracted_video(
            "https://example.com/video_4K.mp4", "http"
        )
        assert video.quality == "4K"

    def test_no_quality(self):
        """测试无质量信息"""
        extractor = VideoURLExtractor()
        video = extractor._create_extracted_video(
            "https://example.com/video.mp4", "http"
        )
        assert video.quality is None
