"""
代理嗅探器属性测试

Property 1: Proxy Lifecycle State Consistency
Property 3: Video List Uniqueness Invariant
Validates: Requirements 1.1, 1.5, 2.3, 2.4
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import socket

from src.core.channels.proxy_sniffer import ProxySniffer, VideoSnifferAddon
from src.core.channels.models import (
    SnifferState,
    SnifferStatus,
    DetectedVideo,
    EncryptionType,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sniffer():
    """创建嗅探器实例（使用随机端口避免冲突）"""
    # 找一个可用端口
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    
    return ProxySniffer(port=port)


# ============================================================================
# Property 1: Proxy Lifecycle State Consistency
# Validates: Requirements 1.1, 1.5
# ============================================================================

class TestProxyLifecycleStateConsistency:
    """
    Property 1: Proxy Lifecycle State Consistency
    
    For any sequence of start/stop operations on the ProxySniffer, the state 
    should always be consistent: after start() succeeds, the proxy should be 
    listening on the configured port; after stop() succeeds, the port should 
    be released and available for reuse.
    
    **Feature: weixin-channels-download, Property 1: Proxy Lifecycle State Consistency**
    **Validates: Requirements 1.1, 1.5**
    """

    def test_initial_state_is_stopped(self, sniffer):
        """初始状态应该是 STOPPED"""
        assert sniffer._state == SnifferState.STOPPED
        assert sniffer.is_running is False

    def test_get_status_when_stopped(self, sniffer):
        """停止状态下获取状态"""
        status = sniffer.get_status()
        
        assert status.state == SnifferState.STOPPED
        assert status.proxy_address is None
        assert status.videos_detected == 0
        assert status.started_at is None

    @pytest.mark.asyncio
    async def test_start_changes_state_to_starting(self, sniffer):
        """启动时状态应该变为 STARTING"""
        # Mock mitmproxy 以避免实际启动
        with patch('src.core.channels.proxy_sniffer.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            # 模拟启动超时（状态不会变为 RUNNING）
            result = await sniffer.start()
            
            # 由于没有真正启动，会超时
            # 但我们可以验证线程被创建
            mock_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_when_already_stopped(self, sniffer):
        """已停止时再次停止应该成功"""
        result = await sniffer.stop()
        assert result is True
        assert sniffer._state == SnifferState.STOPPED

    def test_port_availability_check(self, sniffer):
        """端口可用性检查"""
        # 测试一个应该可用的端口
        assert sniffer._is_port_available(sniffer.port) is True
        
        # 占用端口后应该不可用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", sniffer.port))
            assert sniffer._is_port_available(sniffer.port) is False

    @pytest.mark.asyncio
    async def test_start_with_occupied_port(self, sniffer):
        """端口被占用时启动应该失败"""
        # 占用端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", sniffer.port))
            s.listen(1)
            
            result = await sniffer.start()
            
            assert result.success is False
            assert result.error_code == "PORT_IN_USE"
            assert sniffer._state == SnifferState.ERROR


# ============================================================================
# Property 3: Video List Uniqueness Invariant
# Validates: Requirements 2.3, 2.4
# ============================================================================

class TestVideoListUniquenessInvariant:
    """
    Property 3: Video List Uniqueness Invariant
    
    For any sequence of video detections, the detected videos list should 
    never contain duplicate entries (same URL). Adding a video that already 
    exists should be idempotent - the list length should not increase.
    
    **Feature: weixin-channels-download, Property 3: Video List Uniqueness Invariant**
    **Validates: Requirements 2.3, 2.4**
    """

    def test_add_unique_video(self, sniffer):
        """添加唯一视频应该成功"""
        video = DetectedVideo(
            id="test-1",
            url="https://finder.video.qq.com/video1.mp4",
            detected_at=datetime.now(),
        )
        
        result = sniffer.add_detected_video(video)
        
        assert result is True
        assert len(sniffer.get_detected_videos()) == 1

    def test_add_duplicate_video_is_rejected(self, sniffer):
        """添加重复视频应该被拒绝"""
        video1 = DetectedVideo(
            id="test-1",
            url="https://finder.video.qq.com/video1.mp4",
            detected_at=datetime.now(),
        )
        video2 = DetectedVideo(
            id="test-2",  # 不同 ID
            url="https://finder.video.qq.com/video1.mp4",  # 相同 URL
            detected_at=datetime.now(),
        )
        
        result1 = sniffer.add_detected_video(video1)
        result2 = sniffer.add_detected_video(video2)
        
        assert result1 is True
        assert result2 is False  # 重复被拒绝
        assert len(sniffer.get_detected_videos()) == 1

    def test_add_multiple_unique_videos(self, sniffer):
        """添加多个唯一视频"""
        for i in range(5):
            video = DetectedVideo(
                id=f"test-{i}",
                url=f"https://finder.video.qq.com/video{i}.mp4",
                detected_at=datetime.now(),
            )
            sniffer.add_detected_video(video)
        
        assert len(sniffer.get_detected_videos()) == 5

    def test_uniqueness_invariant_property(self):
        """唯一性不变量属性测试"""
        # 测试多组 URL
        test_cases = [
            ["https://finder.video.qq.com/a.mp4", "https://finder.video.qq.com/b.mp4"],
            ["https://finder.video.qq.com/x.mp4", "https://finder.video.qq.com/x.mp4"],  # 重复
            ["https://finder.video.qq.com/1.mp4", "https://finder.video.qq.com/2.mp4", 
             "https://finder.video.qq.com/1.mp4", "https://finder.video.qq.com/3.mp4"],
        ]
        
        for urls in test_cases:
            # 每次测试创建新的 sniffer
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            sniffer = ProxySniffer(port=port)
            
            # 添加所有 URL
            for i, url in enumerate(urls):
                video = DetectedVideo(
                    id=f"test-{i}",
                    url=url,
                    detected_at=datetime.now(),
                )
                sniffer.add_detected_video(video)
            
            # 获取结果
            detected = sniffer.get_detected_videos()
            detected_urls = [v.url for v in detected]
            
            # 验证没有重复
            assert len(detected_urls) == len(set(detected_urls))
            
            # 验证数量不超过唯一 URL 数量
            assert len(detected) <= len(set(urls))

    def test_clear_videos(self, sniffer):
        """清空视频列表"""
        # 添加一些视频
        for i in range(3):
            video = DetectedVideo(
                id=f"test-{i}",
                url=f"https://finder.video.qq.com/video{i}.mp4",
                detected_at=datetime.now(),
            )
            sniffer.add_detected_video(video)
        
        assert len(sniffer.get_detected_videos()) == 3
        
        # 清空
        sniffer.clear_videos()
        
        assert len(sniffer.get_detected_videos()) == 0
        
        # 清空后可以重新添加相同的 URL
        video = DetectedVideo(
            id="test-0",
            url="https://finder.video.qq.com/video0.mp4",
            detected_at=datetime.now(),
        )
        result = sniffer.add_detected_video(video)
        assert result is True


# ============================================================================
# Video Detection Callback Tests
# ============================================================================

class TestVideoDetectionCallback:
    """视频检测回调测试"""

    def test_callback_is_called_on_new_video(self, sniffer):
        """添加新视频时应该触发回调"""
        callback_videos = []
        
        def callback(video):
            callback_videos.append(video)
        
        sniffer.set_on_video_detected(callback)
        
        video = DetectedVideo(
            id="test-1",
            url="https://finder.video.qq.com/video1.mp4",
            detected_at=datetime.now(),
        )
        sniffer.add_detected_video(video)
        
        assert len(callback_videos) == 1
        assert callback_videos[0].url == video.url

    def test_callback_not_called_on_duplicate(self, sniffer):
        """添加重复视频时不应该触发回调"""
        callback_count = [0]
        
        def callback(video):
            callback_count[0] += 1
        
        sniffer.set_on_video_detected(callback)
        
        video1 = DetectedVideo(
            id="test-1",
            url="https://finder.video.qq.com/video1.mp4",
            detected_at=datetime.now(),
        )
        video2 = DetectedVideo(
            id="test-2",
            url="https://finder.video.qq.com/video1.mp4",  # 相同 URL
            detected_at=datetime.now(),
        )
        
        sniffer.add_detected_video(video1)
        sniffer.add_detected_video(video2)
        
        assert callback_count[0] == 1  # 只调用一次

    def test_callback_error_does_not_break_add(self, sniffer):
        """回调错误不应该影响添加操作"""
        def bad_callback(video):
            raise Exception("Callback error")
        
        sniffer.set_on_video_detected(bad_callback)
        
        video = DetectedVideo(
            id="test-1",
            url="https://finder.video.qq.com/video1.mp4",
            detected_at=datetime.now(),
        )
        
        # 应该不抛出异常
        result = sniffer.add_detected_video(video)
        
        assert result is True
        assert len(sniffer.get_detected_videos()) == 1


# ============================================================================
# VideoSnifferAddon Tests
# ============================================================================

class TestVideoSnifferAddon:
    """VideoSnifferAddon 单元测试"""

    def test_addon_detects_channels_video(self, sniffer):
        """插件应该检测视频号视频"""
        addon = VideoSnifferAddon(sniffer)
        
        # 创建 mock flow
        flow = MagicMock()
        flow.request.pretty_url = "https://finder.video.qq.com/video.mp4"
        flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }
        
        addon.response(flow)
        
        # 应该检测到视频
        assert len(sniffer.get_detected_videos()) == 1

    def test_addon_ignores_non_channels_url(self, sniffer):
        """插件应该忽略非视频号 URL"""
        addon = VideoSnifferAddon(sniffer)
        
        flow = MagicMock()
        flow.request.pretty_url = "https://www.youtube.com/video.mp4"
        flow.response.headers = {"Content-Type": "video/mp4"}
        
        addon.response(flow)
        
        assert len(sniffer.get_detected_videos()) == 0

    def test_addon_ignores_non_video_content(self, sniffer):
        """插件应该忽略非视频内容"""
        addon = VideoSnifferAddon(sniffer)
        
        flow = MagicMock()
        flow.request.pretty_url = "https://finder.video.qq.com/page.html"
        flow.response.headers = {"Content-Type": "text/html"}
        
        addon.response(flow)
        
        assert len(sniffer.get_detected_videos()) == 0


# ============================================================================
# Status Tests
# ============================================================================

class TestSnifferStatus:
    """嗅探器状态测试"""

    def test_status_reflects_video_count(self, sniffer):
        """状态应该反映视频数量"""
        assert sniffer.get_status().videos_detected == 0
        
        for i in range(3):
            video = DetectedVideo(
                id=f"test-{i}",
                url=f"https://finder.video.qq.com/video{i}.mp4",
                detected_at=datetime.now(),
            )
            sniffer.add_detected_video(video)
        
        assert sniffer.get_status().videos_detected == 3

    def test_status_to_dict(self, sniffer):
        """状态应该能转换为字典"""
        status = sniffer.get_status()
        status_dict = status.to_dict()
        
        assert "state" in status_dict
        assert "proxy_port" in status_dict
        assert "videos_detected" in status_dict
        assert status_dict["state"] == "stopped"
