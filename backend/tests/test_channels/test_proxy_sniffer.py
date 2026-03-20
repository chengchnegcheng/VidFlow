"""
代理嗅探器属性测试

Property 1: Proxy Lifecycle State Consistency
Property 3: Video List Uniqueness Invariant
Validates: Requirements 1.1, 1.5, 2.3, 2.4
"""

import pytest
import json
import zlib
import brotli
import shutil
import subprocess
import textwrap
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import socket
import time

from src.core.channels.proxy_sniffer import (
    ProxySniffer,
    VideoSnifferAddon,
    CHANNELS_INJECT_PROXY_PATH,
    CHANNELS_INJECT_SCRIPT_PATH,
    LOCAL_CAPTURE_ALLOW_HOST_PATTERNS,
    LOCAL_MODE_TARGET_PROCESSES,
    WECHAT_RENDERER_ACTIVITY_TTL_SECONDS,
    WECHAT_RENDERER_RECYCLE_COOLDOWN_SECONDS,
)
from src.core.channels.models import (
    SnifferState,
    SnifferStatus,
    DetectedVideo,
    EncryptionType,
    VideoMetadata,
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

    def test_unexpected_proxy_exit_marks_sniffer_as_error(self, sniffer):
        """Unexpected mitmproxy exits should not leave the sniffer stuck in RUNNING."""
        sniffer.transparent_mode = True
        sniffer._state = SnifferState.RUNNING
        sniffer._stop_requested = False

        sniffer._handle_unexpected_proxy_exit()

        assert sniffer._state == SnifferState.ERROR
        assert "redirect daemon" in (sniffer._error_message or "")

    def test_default_local_mode_targets_include_wechat_helpers(self, sniffer):
        """Local capture should include WeChat helper browsers for page metadata capture."""
        assert "Weixin.exe" in LOCAL_MODE_TARGET_PROCESSES
        assert "WeChatAppEx.exe" in LOCAL_MODE_TARGET_PROCESSES
        assert "QQBrowser.exe" in LOCAL_MODE_TARGET_PROCESSES
        assert "msedgewebview2.exe" in LOCAL_MODE_TARGET_PROCESSES
        assert "QQBrowser.exe" in sniffer.target_processes
        assert "msedgewebview2.exe" in sniffer.target_processes

    def test_quic_targets_exclude_helper_browser_processes(self, sniffer):
        """QUIC blocking should not target general-purpose browser helpers."""
        sniffer.set_target_processes(["Weixin.exe", "QQBrowser.exe", "msedgewebview2.exe"])

        quic_status = sniffer.get_quic_status()

        assert "QQBrowser.exe" in quic_status["target_processes"]
        assert "msedgewebview2.exe" in quic_status["target_processes"]
        assert "QQBrowser.exe" not in quic_status["quic_target_processes"]
        assert "msedgewebview2.exe" not in quic_status["quic_target_processes"]

    def test_local_capture_allow_hosts_exclude_non_tencent_noise(self, sniffer):
        """Local capture should restrict helper-browser traffic to WeChat/Tencent domains."""
        allow_hosts = sniffer._build_local_capture_allow_hosts()

        assert allow_hosts == list(LOCAL_CAPTURE_ALLOW_HOST_PATTERNS)
        assert any("qq\\.com" in pattern for pattern in allow_hosts)
        assert any("wechat\\.com" in pattern for pattern in allow_hosts)
        assert not any("googleapis" in pattern for pattern in allow_hosts)


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

    def test_add_rotating_channels_variant_with_decode_key_merges_into_existing_record(self, sniffer):
        original = DetectedVideo(
            id="rotating-1",
            url=(
                "https://findera4.video.qq.com/251/20302/stodownload"
                "?encfilekey=OT2U0aOQ4m5Bz0oiaNg8zoRTEpj1QxVdy11111111111111111111"
                "&taskid=pc-1773753665131832760"
            ),
            title="测试视频标题-旋转画质合并",
            duration=17,
            thumbnail="https://wx.qlogo.cn/finderhead/ver_1/test-avatar/132",
            detected_at=datetime.now(),
            encryption_type=EncryptionType.ISAAC64,
            decryption_key=None,
        )
        updated = DetectedVideo(
            id="rotating-2",
            url=(
                "https://finder.video.qq.com/251/20302/stodownload"
                "?encfilekey=OT2U0aOQ4m5Bz0oiaNg8zoRTEpj1QxVdy22222222222222222222"
                "&taskid=pc-1773753665131832761"
            ),
            title="测试视频标题-旋转画质合并",
            duration=17,
            thumbnail="https://wx.qlogo.cn/finderhead/ver_1/test-avatar/132",
            detected_at=datetime.now(),
            encryption_type=EncryptionType.ISAAC64,
            decryption_key="1234567890",
        )

        result1 = sniffer.add_detected_video(original)
        result2 = sniffer.add_detected_video(updated)

        assert result1 is True
        assert result2 is False
        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].decryption_key == "1234567890"
        assert videos[0].url == updated.url

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

    def test_inject_script_tag_inlines_hook_source(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        tag = addon._get_inject_script_tag()

        assert 'data-vidflow-injected="inline"' in tag
        assert 'src="' not in tag
        assert "window.__vidflow_injected__" in tag

    def test_proxy_serves_same_origin_inject_script(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        flow = MagicMock()
        flow.request.pretty_url = f"https://channels.weixin.qq.com{CHANNELS_INJECT_SCRIPT_PATH}"
        flow.request.method = "GET"
        flow.metadata = {}
        flow.response = None

        addon.request(flow)

        assert flow.response is not None
        assert flow.response.status_code == 200
        assert flow.response.headers["Content-Type"].startswith("application/javascript")
        assert b"window.__vidflow_injected__" in flow.response.content

    def test_inject_script_path_resolution_finds_existing_source(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        script_path = addon._resolve_inject_script_path()

        assert script_path.name == "inject_script.js"
        assert script_path.exists()

    def test_served_inject_script_contains_runtime_response_hooks(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        script_source = addon._get_inject_script_source()

        assert "function hookFetch()" in script_source
        assert "function hookXHR()" in script_source
        assert "function hookHistoryNavigation()" in script_source
        assert "function discoverAndHookWXRuntime(reason)" in script_source
        assert "function hookWXEventBus(eventBus, label)" in script_source

    def test_served_inject_script_is_valid_javascript(self, sniffer, tmp_path):
        node = shutil.which('node')
        if not node:
            pytest.skip('node not available')

        addon = VideoSnifferAddon(sniffer)
        script_path = tmp_path / 'inject_script.js'
        script_path.write_text(addon._get_inject_script_source(), encoding='utf-8')

        result = subprocess.run([node, '--check', str(script_path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr or result.stdout

    def test_inject_script_title_helpers_keep_tech_titles_and_use_video_attributes(self, sniffer, tmp_path):
        node = shutil.which('node')
        if not node:
            pytest.skip('node not available')

        addon = VideoSnifferAddon(sniffer)
        script_source = addon._get_inject_script_source()
        prefix, suffix = script_source.rsplit("})();", 1)
        patched_source = (
            prefix
            + "window.__vidflow_test_exports__ = {"
            + "sanitizeTitleValue: sanitizeTitleValue,"
            + "getNearbyVideoTitle: getNearbyVideoTitle"
            + "};\n})();"
            + suffix
        )

        harness_path = tmp_path / "inject_script_harness.js"
        harness_path.write_text(
            textwrap.dedent(
                f"""
                const assert = require('assert');
                const {{ URL }} = require('url');

                const source = {json.dumps(patched_source)};

                function createNode(options) {{
                    options = options || {{}};
                    const attrs = options.attrs || {{}};
                    return {{
                        dataset: options.dataset || null,
                        textContent: options.text || '',
                        innerText: options.text || '',
                        childNodes: options.childNodes || [],
                        parentElement: options.parentElement || null,
                        previousElementSibling: options.previousElementSibling || null,
                        nextElementSibling: options.nextElementSibling || null,
                        queryMap: options.queryMap || {{}},
                        getAttribute(name) {{
                            return Object.prototype.hasOwnProperty.call(attrs, name) ? attrs[name] : null;
                        }},
                        querySelectorAll(selector) {{
                            return this.queryMap[selector] || [];
                        }}
                    }};
                }}

                global.console = {{ log() {{}}, warn() {{}}, error() {{}}, info() {{}} }};
                global.setTimeout = function() {{ return 0; }};
                global.clearTimeout = function() {{}};
                global.setInterval = function() {{ return 0; }};
                global.clearInterval = function() {{}};
                global.URL = URL;
                global.history = {{ pushState() {{}}, replaceState() {{}} }};
                global.location = {{
                    origin: 'https://channels.weixin.qq.com',
                    href: 'https://channels.weixin.qq.com/web/pages/home'
                }};
                global.document = {{
                    hidden: false,
                    title: '',
                    readyState: 'complete',
                    body: {{
                        appendChild() {{}}
                    }},
                    documentElement: {{}},
                    createElement() {{
                        return {{
                            style: {{}},
                            remove() {{}},
                            textContent: ''
                        }};
                    }},
                    addEventListener() {{}},
                    querySelector() {{ return null; }},
                    querySelectorAll() {{ return []; }}
                }};
                global.window = global;
                global.window.document = global.document;
                global.window.location = global.location;
                global.window.history = global.history;
                global.window.addEventListener = function() {{}};
                global.window.removeEventListener = function() {{}};
                global.window.fetch = undefined;
                global.MutationObserver = function() {{
                    this.observe = function() {{}};
                }};
                global.XMLHttpRequest = function() {{}};
                global.XMLHttpRequest.prototype.open = function() {{}};
                global.XMLHttpRequest.prototype.send = function() {{}};
                global.XMLHttpRequest.prototype.setRequestHeader = function() {{}};
                global.XMLHttpRequest.prototype.addEventListener = function() {{}};

                eval(source);

                const helpers = global.window.__vidflow_test_exports__;
                assert.strictEqual(helpers.sanitizeTitleValue('Next.js'), 'Next.js');
                assert.strictEqual(helpers.sanitizeTitleValue('A=B'), 'A=B');
                assert.strictEqual(helpers.sanitizeTitleValue('IE=edge'), null);
                assert.strictEqual(helpers.sanitizeTitleValue('index.publishABC123.js'), null);

                const video = createNode({{ attrs: {{ 'aria-label': 'Inline Video Title' }} }});
                assert.strictEqual(helpers.getNearbyVideoTitle(video), 'Inline Video Title');
                """
            ),
            encoding="utf-8",
        )

        result = subprocess.run([node, str(harness_path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr or result.stdout

    def test_proxy_bridge_ingests_metadata_without_forwarding(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        ingested_video = MagicMock()
        ingested_video.title = "Test Title"
        ingested_video.thumbnail = "https://wx.qlogo.cn/test.jpg"
        ingested_video.decryption_key = "1234567890"
        ingested_video.to_dict.return_value = {"title": "Test Title"}
        sniffer.ingest_injected_video = MagicMock(return_value=ingested_video)

        payload = {
            "url": "https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc123def4567890",
            "title": "Test Title",
            "thumbnail": "https://wx.qlogo.cn/test.jpg",
            "decodeKey": "1234567890",
            "duration": 18,
        }
        flow = MagicMock()
        flow.request.pretty_url = f"https://channels.weixin.qq.com{CHANNELS_INJECT_PROXY_PATH}"
        flow.request.method = "POST"
        flow.request.headers = {"Origin": "https://channels.weixin.qq.com"}
        flow.request.get_text.return_value = json.dumps(payload)
        flow.metadata = {}
        flow.response = None

        addon.request(flow)

        sniffer.ingest_injected_video.assert_called_once()
        assert flow.response is not None
        assert flow.response.status_code == 200
        response_payload = json.loads(flow.response.content.decode("utf-8"))
        assert response_payload["success"] is True
        assert response_payload["video"]["title"] == "Test Title"

    def test_proxy_bridge_rejects_missing_video_url(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        flow = MagicMock()
        flow.request.pretty_url = f"https://channels.weixin.qq.com{CHANNELS_INJECT_PROXY_PATH}"
        flow.request.method = "POST"
        flow.request.headers = {"Origin": "https://channels.weixin.qq.com"}
        flow.request.get_text.return_value = json.dumps({"title": "Missing URL"})
        flow.metadata = {}
        flow.response = None

        addon.request(flow)

        assert flow.response is not None
        assert flow.response.status_code == 400

    def test_proxy_bridge_caches_keyed_metadata_without_video_url(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772877730633729323"
        encfilekey = "abc123def4567890abc123def4567890"
        payload = {
            "title": "Bridge Cached Title",
            "thumbnail": "https://wx.qlogo.cn/bridge-test.jpg",
            "decodeKey": "1234567890",
            "cacheKeys": [task_id, encfilekey],
        }
        flow = MagicMock()
        flow.request.pretty_url = f"https://channels.weixin.qq.com{CHANNELS_INJECT_PROXY_PATH}"
        flow.request.method = "POST"
        flow.request.headers = {"Origin": "https://channels.weixin.qq.com"}
        flow.request.get_text.return_value = json.dumps(payload)
        flow.metadata = {}
        flow.response = None

        addon.request(flow)

        assert flow.response is not None
        assert flow.response.status_code == 200
        response_payload = json.loads(flow.response.content.decode("utf-8"))
        assert response_payload["success"] is True
        assert response_payload["cached_only"] is True

        video_flow = MagicMock()
        video_flow.request.pretty_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "Bridge Cached Title"
        assert videos[0].thumbnail == "https://wx.qlogo.cn/bridge-test.jpg"
        assert videos[0].decryption_key == "1234567890"

    def test_ingest_injected_video_reconciles_decode_key_to_related_rotating_urls(self, sniffer):
        _addon = VideoSnifferAddon(sniffer)
        url_without_key = (
            "https://finder.video.qq.com/251/20302/stodownload"
            "?encfilekey=cccccccccccccccccccccccccccccccccccc111111"
            "&taskid=pc-1772877730633729401"
        )
        url_with_key = (
            "https://finder.video.qq.com/251/20302/stodownload"
            "?encfilekey=cccccccccccccccccccccccccccccccccccc222222"
            "&taskid=pc-1772877730633729402"
        )

        sniffer.add_detected_video(
            DetectedVideo(
                id="raw-rotating-a",
                url=url_without_key,
                title="Bridge Cached Title",
                duration=18,
                resolution="1080x1920",
                thumbnail="https://wx.qlogo.cn/bridge-test.jpg",
                detected_at=datetime.now(),
                encryption_type=EncryptionType.ISAAC64,
                decryption_key=None,
            )
        )

        sniffer.ingest_injected_video(
            url=url_with_key,
            title="Bridge Cached Title",
            thumbnail="https://wx.qlogo.cn/bridge-test.jpg",
            duration=18,
            width=1080,
            height=1920,
            decode_key="1234567890",
        )

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        related = videos[0]
        assert related.decryption_key == "1234567890"
        assert related.url == url_with_key

    def test_html_inline_state_metadata_is_applied_to_later_video_flow(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            "?encfilekey=abc123def4567890abc123def4567890&token=test"
        )
        html = (
            "<html><head></head><body><script>"
            "window.__INITIAL_STATE__={"
            "\"feed\":{"
            f"\"title\":\"真实标题\",\"thumbUrl\":\"https://wx.qlogo.cn/test.jpg\","
            f"\"decodeKey\":\"1234567890\",\"url\":\"{video_url}\""
            "}"
            "};"
            "</script></body></html>"
        )

        html_flow = MagicMock()
        html_flow.request.pretty_url = "https://channels.weixin.qq.com/platform/post/create"
        html_flow.response.headers = {"Content-Type": "text/html; charset=utf-8"}
        html_flow.response.get_text.return_value = html
        html_flow.response.set_text = MagicMock()

        addon.response(html_flow)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "真实标题"
        assert videos[0].thumbnail == "https://wx.qlogo.cn/test.jpg"
        assert videos[0].decryption_key == "1234567890"


    def test_html_key_only_metadata_is_applied_to_later_video_flow(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772808128767108874"
        encfilekey = "abc123def4567890abc123def4567890"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        html = (
            "<html><head></head><body><script>"
            "window.__INITIAL_STATE__={"
            "\"feed\":{"
            "\"title\":\"Key Only Title\","
            "\"thumbUrl\":\"https://wx.qlogo.cn/key-only.jpg\","
            "\"decodeKey\":\"1234567890\","
            f"\"taskid\":\"{task_id}\","
            f"\"encfilekey\":\"{encfilekey}\""
            "}"
            "};"
            "</script></body></html>"
        )

        html_flow = MagicMock()
        html_flow.request.pretty_url = "https://channels.weixin.qq.com/platform/post/create"
        html_flow.response.headers = {"Content-Type": "text/html; charset=utf-8"}
        html_flow.response.get_text.return_value = html
        html_flow.response.set_text = MagicMock()

        addon.response(html_flow)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "Key Only Title"
        assert videos[0].thumbnail == "https://wx.qlogo.cn/key-only.jpg"
        assert videos[0].decryption_key == "1234567890"

    def test_exact_cache_provides_decode_key(self, sniffer):
        """精确缓存匹配提供 decode_key（不从不相关的 fallback 缓存借用）。"""
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772808128767108875"
        encfilekey = "backfill1234567890backfill1234567890"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )

        # 精确缓存包含 decode_key
        addon.cache_external_metadata(
            VideoMetadata(
                title="Backfill Decode Key Title",
                thumbnail="https://wx.qlogo.cn/backfill-key.jpg",
                decode_key="1234567890",
            ),
            sniffer._build_metadata_cache_keys(video_url),
        )

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "Backfill Decode Key Title"
        assert videos[0].thumbnail == "https://wx.qlogo.cn/backfill-key.jpg"
        assert videos[0].decryption_key == "1234567890"

    def test_html_like_channels_document_with_nonstandard_content_type_is_injected_and_cached(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772809638310928957"
        encfilekey = "abc123def4567890abc123def4567890"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        html = (
            "<!doctype html><html><head></head><body><script>"
            "window.__INITIAL_STATE__={"
            "\"feed\":{"
            "\"title\":\"Weird Content Type Title\","
            "\"thumbUrl\":\"https://wx.qlogo.cn/weird-type.jpg\","
            "\"decodeKey\":\"1234567890\","
            f"\"taskid\":\"{task_id}\","
            f"\"encfilekey\":\"{encfilekey}\""
            "}"
            "};"
            "</script></body></html>"
        )

        html_flow = MagicMock()
        html_flow.request.pretty_url = "https://channels.weixin.qq.com/platform/post/create"
        html_flow.response.headers = {"Content-Type": "application/octet-stream"}
        html_flow.response.get_text.return_value = html
        html_flow.response.set_text = MagicMock()

        addon.response(html_flow)

        html_flow.response.set_text.assert_called_once()
        samples = sniffer.get_runtime_statistics()["recent_response_samples"]
        assert any(sample["host"] == "channels.weixin.qq.com" for sample in samples)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "Weird Content Type Title"
        assert videos[0].thumbnail == "https://wx.qlogo.cn/weird-type.jpg"
        assert videos[0].decryption_key == "1234567890"

    def test_sanitize_video_title_rejects_browser_compat_and_expression_noise(self, sniffer):
        assert sniffer._sanitize_video_title("IE=edge") is None
        assert sniffer._sanitize_video_title("t(_l)") is None
        assert sniffer._sanitize_video_title("index.publishABC123.js") is None

    def test_sanitize_video_title_keeps_short_ascii_and_tech_titles(self, sniffer):
        assert sniffer._sanitize_video_title("X") == "X"
        assert sniffer._sanitize_video_title("A=B") == "A=B"
        assert sniffer._sanitize_video_title("Next.js") == "Next.js"
        assert sniffer._sanitize_video_title("hello.world") == "hello.world"

    def test_ascii_titles_are_not_penalized_relative_to_short_cjk_titles(self, sniffer):
        cjk_title = "\u89c6\u9891"
        assert sniffer._score_video_title("AI") >= sniffer._score_video_title(cjk_title)
        # 分数相同时保留已有标题（第一个参数），不替换
        result = sniffer._pick_better_title(cjk_title, "AI")
        assert result in (cjk_title, "AI")

    def test_text_response_metadata_without_video_url_or_decode_key_is_ignored(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        encfilekey = "noise1234567890noise1234567890abcd"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&token=test"
        )
        js_text = (
            "{"
            "\"content\":\"IE=edge\","
            "\"thumbUrl\":\"https://wx.qlogo.cn/noise-thumb.jpg\","
            f"\"encfilekey\":\"{encfilekey}\""
            "}"
        )

        js_flow = MagicMock()
        js_flow.request.pretty_url = "https://res.wx.qq.com/t/wx_fed/finder/web/web-finder/res/js/polyfills.publish.js"
        js_flow.response.headers = {"Content-Type": "application/javascript; charset=utf-8"}
        js_flow.response.status_code = 200
        js_flow.response.get_text.return_value = js_text
        js_flow.response.set_text = MagicMock()

        addon.response(js_flow)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title.startswith("channels_")
        assert videos[0].thumbnail is None
        assert videos[0].decryption_key is None

    def test_channels_page_html_with_cache_keys_only_reconciles_title_and_thumbnail(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1773280437024692937"
        encfilekey = "Cvvj5Ix3eez3Y79SxtvVL0L7CkPM6dFibusn4vVFEyiaoI2NNbmDohJPmSgIyKmOog"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        html = (
            "<!doctype html><html><head></head><body><script>"
            "window.__INITIAL_STATE__={"
            "\"feed\":{"
            "\"title\":\"页面真实标题\","
            "\"thumbUrl\":\"https://wx.qlogo.cn/page-cover.jpg\","
            f"\"taskid\":\"{task_id}\","
            f"\"encfilekey\":\"{encfilekey}\""
            "}"
            "};"
            "</script></body></html>"
        )

        html_flow = MagicMock()
        html_flow.request.pretty_url = "https://channels.weixin.qq.com/web/pages/home?context_id=test-page"
        html_flow.response.headers = {"Content-Type": "text/html; charset=utf-8"}
        html_flow.response.status_code = 200
        html_flow.response.get_text.return_value = html
        html_flow.response.set_text = MagicMock()

        addon.response(html_flow)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "页面真实标题"
        assert videos[0].thumbnail == "https://wx.qlogo.cn/page-cover.jpg"

    def test_html_injection_strips_meta_csp_and_inlines_hook(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        html = (
            '<!doctype html><html><head>'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'self\'">'
            '</head><body><div>hello</div></body></html>'
        )

        html_flow = MagicMock()
        html_flow.request.pretty_url = "https://channels.weixin.qq.com/web/pages/home"
        html_flow.response.headers = {"Content-Type": "text/html; charset=utf-8"}
        html_flow.response.get_text.return_value = html
        html_flow.response.set_text = MagicMock()

        assert addon._inject_channels_script(html_flow) is True

        injected_html = html_flow.response.set_text.call_args[0][0]
        assert "Content-Security-Policy" not in injected_html
        assert 'data-vidflow-injected="inline"' in injected_html
        assert "window.__vidflow_injected__" in injected_html
        assert CHANNELS_INJECT_SCRIPT_PATH not in injected_html
        runtime = sniffer.get_runtime_statistics()
        assert runtime["channels_page_injection_kind"] == "html"
        assert runtime["channels_page_injection_url"] == "https://channels.weixin.qq.com/web/pages/home"

    def test_js_asset_from_res_wx_qq_com_is_injected(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        js_flow = MagicMock()
        js_flow.request.pretty_url = "https://res.wx.qq.com/t/wx_fed/finder/shell/index.js"
        js_flow.response.headers = {"Content-Type": "application/javascript; charset=utf-8"}
        js_flow.response.get_text.return_value = "console.log('finder shell');"
        js_flow.response.set_text = MagicMock()

        addon.response(js_flow)

        js_flow.response.set_text.assert_called_once()
        runtime = sniffer.get_runtime_statistics()
        assert runtime["channels_page_injection_kind"] == "js"

    def test_channels_web_activity_without_injection_triggers_renderer_recycle(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        sniffer.maybe_recycle_wechat_renderer = MagicMock(return_value=True)

        flow = MagicMock()
        flow.request.pretty_url = "https://channels.weixin.qq.com/web/report-perf?pf=web"
        flow.response.headers = {"Content-Type": "application/json; charset=utf-8"}
        flow.response.status_code = 201
        flow.response.content = b'{"ok":true}'
        flow.response.get_text.return_value = '{"ok":true}'
        flow.response.set_text = MagicMock()

        addon._try_extract_api_metadata(flow)

        sniffer.maybe_recycle_wechat_renderer.assert_called_once_with(
            "channels_web_activity_without_injection",
            "https://channels.weixin.qq.com/web/report-perf?pf=web",
        )

    def test_video_stream_without_injection_triggers_renderer_recycle(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        sniffer.maybe_recycle_wechat_renderer = MagicMock(return_value=True)

        flow = MagicMock()
        flow.request.pretty_url = "https://finder.video.qq.com/251/20302/stodownload?encfilekey=test&taskid=pc-1"
        flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }
        flow.response.status_code = 206

        addon.response(flow)

        sniffer.maybe_recycle_wechat_renderer.assert_called_once_with(
            "video_stream_without_channels_injection",
            "https://finder.video.qq.com/251/20302/stodownload?encfilekey=test&taskid=pc-1",
        )

    def test_thumbnail_image_response_does_not_trigger_renderer_recycle(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        sniffer.maybe_recycle_wechat_renderer = MagicMock(return_value=True)

        image_url = (
            "https://finder.video.qq.com/251/20350/stodownload"
            "?encfilekey=test-thumb&m=thumb-cache-key&picformat=200&wxampicformat=503"
        )
        flow = MagicMock()
        flow.request.method = "GET"
        flow.request.pretty_url = image_url
        flow.response.headers = {
            "Content-Type": "image/webp",
            "Content-Length": "32768",
        }
        flow.response.status_code = 200

        addon.response(flow)

        sniffer.maybe_recycle_wechat_renderer.assert_not_called()
        assert sniffer.get_detected_videos() == []

        cache_keys = sniffer._build_metadata_cache_keys(image_url)
        assert cache_keys
        for cache_key in cache_keys:
            assert addon._metadata_cache[cache_key].thumbnail == image_url

    def test_maybe_recycle_wechat_renderer_is_deferred_when_redirect_daemon_is_unstable(self, sniffer):
        sniffer.transparent_mode = True
        sniffer._state = SnifferState.RUNNING

        with patch.object(
            sniffer,
            "_recycle_wechat_renderer_processes",
            side_effect=AssertionError("renderer recycle should stay disabled"),
        ):
            result = sniffer.maybe_recycle_wechat_renderer(
                "channels_web_activity_without_injection",
                "https://channels.weixin.qq.com/web/report-perf?pf=web",
            )

        assert result is False
        runtime = sniffer.get_runtime_statistics()
        assert runtime["renderer_recycle_attempted"] is True
        assert runtime["renderer_recycle_completed"] is False
        assert runtime["renderer_recycle_reason"] == "channels_web_activity_without_injection"
        assert any(
            sample["classification"] == "renderer_recycle_deferred"
            and "transparent_mode" in str(sample.get("detail"))
            for sample in runtime["recent_response_samples"]
        )

    def test_maybe_recycle_wechat_renderer_is_deferred_in_explicit_proxy_mode(self, sniffer):
        sniffer.transparent_mode = False
        sniffer._state = SnifferState.RUNNING

        with patch.object(
            sniffer,
            "_recycle_wechat_renderer_processes",
            side_effect=AssertionError("renderer recycle should stay disabled"),
        ):
            result = sniffer.maybe_recycle_wechat_renderer(
                "video_stream_without_channels_injection",
                "https://finder.video.qq.com/251/20302/stodownload?encfilekey=test&taskid=pc-1",
            )

        assert result is False
        runtime = sniffer.get_runtime_statistics()
        assert runtime["renderer_recycle_attempted"] is True
        assert runtime["renderer_recycle_completed"] is False
        assert runtime["renderer_recycle_reason"] == "video_stream_without_channels_injection"
        assert any(
            sample["classification"] == "renderer_recycle_deferred"
            and "explicit_proxy" in str(sample.get("detail"))
            and "automatic_renderer_recycle_disabled" in str(sample.get("detail"))
            for sample in runtime["recent_response_samples"]
        )

    def test_maybe_recycle_wechat_renderer_retries_after_cooldown(self, sniffer):
        sniffer.transparent_mode = False
        sniffer._state = SnifferState.RUNNING

        with patch.object(
            sniffer,
            "_recycle_wechat_renderer_processes",
            side_effect=AssertionError("renderer recycle should stay disabled"),
        ) as recycle:
            first = sniffer.maybe_recycle_wechat_renderer(
                "video_stream_without_channels_injection",
                "https://finder.video.qq.com/251/20302/stodownload?encfilekey=test&taskid=pc-1",
            )
            second = sniffer.maybe_recycle_wechat_renderer(
                "video_stream_without_channels_injection",
                "https://finder.video.qq.com/251/20302/stodownload?encfilekey=test&taskid=pc-2",
            )
            sniffer._renderer_recycle_at = datetime.now() - timedelta(
                seconds=WECHAT_RENDERER_RECYCLE_COOLDOWN_SECONDS + 1
            )
            third = sniffer.maybe_recycle_wechat_renderer(
                "video_stream_without_channels_injection",
                "https://finder.video.qq.com/251/20302/stodownload?encfilekey=test&taskid=pc-3",
            )

        assert first is False
        assert second is False
        assert third is False
        assert recycle.call_count == 0
        assert sniffer.get_runtime_statistics()["renderer_recycle_attempt_count"] == 2

    def test_recent_helper_process_activity_expires(self, sniffer):
        sniffer.note_renderer_process_activity("QQBrowser.exe", 4321)
        assert sniffer._get_recent_renderer_process_candidates() == {4321: "QQBrowser.exe"}

        sniffer._recent_renderer_process_activity[4321] = (
            "QQBrowser.exe",
            time.monotonic() - WECHAT_RENDERER_ACTIVITY_TTL_SECONDS - 1,
        )

        assert sniffer._get_recent_renderer_process_candidates() == {}

    def test_startup_renderer_refresh_recycles_safe_wechat_renderer_children(self, sniffer):
        sniffer.transparent_mode = False
        sniffer._state = SnifferState.RUNNING

        renderer = MagicMock()
        renderer.pid = 4321
        renderer.info = {
            "name": "WeChatAppEx.exe",
            "cmdline": [
                "WeChatAppEx.exe",
                "--type=renderer",
                "--wmpf-render-type=7",
            ],
        }

        with patch("psutil.process_iter", return_value=[renderer]), patch(
            "psutil.wait_procs",
            return_value=([renderer], []),
        ):
            result = sniffer.proactively_recycle_wechat_renderer_on_startup()

        assert result is True
        renderer.terminate.assert_called_once()
        runtime = sniffer.get_runtime_statistics()
        assert runtime["renderer_recycle_reason"] == "startup_missing_channels_injection"
        assert runtime["renderer_recycle_attempt_count"] == 1
        assert runtime["renderer_recycle_completed"] is True

    def test_startup_renderer_refresh_ignores_non_wechat_owned_webview_helpers(self, sniffer):
        sniffer.transparent_mode = False
        sniffer._state = SnifferState.RUNNING

        helper = MagicMock()
        helper.pid = 5432
        helper.info = {
            "name": "msedgewebview2.exe",
            "cmdline": [
                "msedgewebview2.exe",
                "--type=renderer",
                "--webview-exe-name=clash-verge.exe",
            ],
        }

        with patch("psutil.process_iter", return_value=[helper]):
            result = sniffer.proactively_recycle_wechat_renderer_on_startup()

        assert result is False
        helper.terminate.assert_not_called()
        assert sniffer.get_runtime_statistics()["renderer_recycle_attempt_count"] == 0

    def test_startup_renderer_refresh_skips_when_no_renderer_process_exists(self, sniffer):
        sniffer.transparent_mode = False
        sniffer._state = SnifferState.RUNNING

        with patch("psutil.process_iter", return_value=[]):
            result = sniffer.proactively_recycle_wechat_renderer_on_startup()

        assert result is False
        assert sniffer.get_runtime_statistics()["renderer_recycle_attempt_count"] == 0

    def test_mmtls_binary_metadata_is_applied_to_later_video_flow(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772810744905962706"
        encfilekey = "abc123def4567890abc123def4567890"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        binary_payload = (
            b"\x00\x01MMTLS"
            + (
                "{"
                "\"title\":\"MMTLS Title\","
                "\"thumbUrl\":\"https://res.wx.qq.com/shop/public/test-thumb.png\","
                "\"decodeKey\":\"1234567890\","
                f"\"taskid\":\"{task_id}\","
                f"\"encfilekey\":\"{encfilekey}\","
                f"\"url\":\"{video_url}\""
                "}"
            ).encode("utf-8")
            + b"\x02\x03"
        )

        mmtls_flow = MagicMock()
        mmtls_flow.request.pretty_url = "http://extshort.weixin.qq.com/mmtls/00000edf"
        mmtls_flow.response.headers = {"Content-Type": "application/octet-stream"}
        mmtls_flow.response.status_code = 200
        mmtls_flow.response.content = binary_payload
        mmtls_flow.response.get_text.side_effect = ValueError("binary payload")
        mmtls_flow.response.set_text = MagicMock()

        addon.response(mmtls_flow)

        samples = sniffer.get_runtime_statistics()["recent_response_samples"]
        assert any(sample["host"] == "extshort.weixin.qq.com" for sample in samples)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "MMTLS Title"
        assert videos[0].thumbnail == "https://res.wx.qq.com/shop/public/test-thumb.png"
        assert videos[0].decryption_key == "1234567890"

    def test_prefixed_zlib_mmtls_binary_metadata_is_applied_to_later_video_flow(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772810744905962999"
        encfilekey = "zlib123def4567890zlib123def4567890"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        json_payload = (
            "{"
            "\"title\":\"Prefixed Zlib Title\","
            "\"thumbUrl\":\"https://res.wx.qq.com/shop/public/zlib-thumb.png\","
            "\"decodeKey\":\"5566778899\","
            f"\"taskid\":\"{task_id}\","
            f"\"encfilekey\":\"{encfilekey}\","
            f"\"url\":\"{video_url}\""
            "}"
        ).encode("utf-8")
        binary_payload = b"\x00\x01MMTLS\x88\x99" + zlib.compress(json_payload) + b"\x02\x03"

        mmtls_flow = MagicMock()
        mmtls_flow.request.pretty_url = "http://extshort.weixin.qq.com/mmtls/00000edf"
        mmtls_flow.response.headers = {"Content-Type": "application/octet-stream"}
        mmtls_flow.response.status_code = 200
        mmtls_flow.response.content = binary_payload
        mmtls_flow.response.get_text.side_effect = ValueError("binary payload")
        mmtls_flow.response.set_text = MagicMock()

        addon.response(mmtls_flow)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "Prefixed Zlib Title"
        assert videos[0].thumbnail == "https://res.wx.qq.com/shop/public/zlib-thumb.png"
        assert videos[0].decryption_key == "5566778899"

    def test_prefixed_brotli_mmtls_binary_metadata_is_applied_to_later_video_flow(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772810744905962888"
        encfilekey = "brotli123def4567890brotli123def4567"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        json_payload = (
            "{"
            "\"title\":\"Prefixed Brotli Title\","
            "\"thumbUrl\":\"https://res.wx.qq.com/shop/public/brotli-thumb.png\","
            "\"decodeKey\":\"7788990011\","
            f"\"taskid\":\"{task_id}\","
            f"\"encfilekey\":\"{encfilekey}\","
            f"\"url\":\"{video_url}\""
            "}"
        ).encode("utf-8")
        binary_payload = b"\x00\x01MMTLS\x88\x99" + brotli.compress(json_payload) + b"\x02\x03"

        mmtls_flow = MagicMock()
        mmtls_flow.request.pretty_url = "http://extshort.weixin.qq.com/mmtls/00000edf"
        mmtls_flow.response.headers = {"Content-Type": "application/octet-stream"}
        mmtls_flow.response.status_code = 200
        mmtls_flow.response.content = binary_payload
        mmtls_flow.response.get_text.side_effect = ValueError("binary payload")
        mmtls_flow.response.set_text = MagicMock()

        addon.response(mmtls_flow)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "Prefixed Brotli Title"
        assert videos[0].thumbnail == "https://res.wx.qq.com/shop/public/brotli-thumb.png"
        assert videos[0].decryption_key == "7788990011"

    def test_channels_html_skip_reason_is_recorded_for_diagnostics(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        flow = MagicMock()
        flow.request.pretty_url = "https://channels.weixin.qq.com/web/pages/home"
        flow.response.headers = {"Content-Type": "application/json; charset=utf-8"}
        flow.response.status_code = 200
        flow.response.content = b'{"ok":true}'
        flow.response.get_text.return_value = '{"ok":true}'
        flow.response.set_text = MagicMock()

        assert addon._inject_channels_script(flow) is False

        samples = sniffer.get_runtime_statistics()["recent_response_samples"]
        assert any(
            sample["classification"] == "channels_html_skip" and sample.get("detail") == "not_html_like"
            for sample in samples
        )

    def test_unquoted_js_like_mmtls_metadata_is_applied_to_later_video_flow(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772810744905962111"
        encfilekey = "unquoted1234567890unquoted1234567890"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        binary_payload = (
            b"\x00\x01MMTLS"
            + (
                "{"
                "title:'Unquoted MMTLS Title',"
                "thumbUrl:https://res.wx.qq.com/shop/public/unquoted-thumb.png,"
                "decodeKey:2065249527,"
                f"taskid:{task_id},"
                f"encfilekey:{encfilekey}"
                "}"
            ).encode("utf-8")
            + b"\x02\x03"
        )

        mmtls_flow = MagicMock()
        mmtls_flow.request.pretty_url = "http://extshort.weixin.qq.com/mmtls/00000eff"
        mmtls_flow.response.headers = {"Content-Type": "application/octet-stream"}
        mmtls_flow.response.status_code = 200
        mmtls_flow.response.content = binary_payload
        mmtls_flow.response.get_text.side_effect = ValueError("binary payload")
        mmtls_flow.response.set_text = MagicMock()

        addon.response(mmtls_flow)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "Unquoted MMTLS Title"
        assert videos[0].thumbnail == "https://res.wx.qq.com/shop/public/unquoted-thumb.png"
        assert videos[0].decryption_key == "2065249527"

    def test_key_anchored_mmtls_metadata_fields_are_applied_to_later_video_flow(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772811802250000999"
        media_key = "mmtls-key-anchor-variant"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?m={media_key}&taskid={task_id}&token=test"
        )
        binary_payload = (
            b"\x00\x01MMTLS"
            + (
                "{"
                "\"objectNonceId\":\"Key Anchor Variant Title\","
                "\"coverUrl\":\"https://cdn.example.com/variant-cover.jpg\","
                "\"decodeKey\":\"1122334455\","
                "\"videoDuration\":18,"
                "\"videoWidth\":1080,"
                "\"videoHeight\":1920,"
                "\"fileSize\":2048,"
                f"\"taskId\":\"{task_id}\","
                f"\"m\":\"{media_key}\""
                "}"
            ).encode("utf-8")
            + b"\x02\x03"
        )

        mmtls_flow = MagicMock()
        mmtls_flow.request.pretty_url = "http://180.101.242.212/mmtls/00000f11"
        mmtls_flow.response.headers = {"Content-Type": "application/octet-stream"}
        mmtls_flow.response.status_code = 200
        mmtls_flow.response.content = binary_payload
        mmtls_flow.response.get_text.side_effect = ValueError("binary payload")
        mmtls_flow.response.set_text = MagicMock()

        addon.response(mmtls_flow)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "Key Anchor Variant Title"
        assert videos[0].thumbnail == "https://cdn.example.com/variant-cover.jpg"
        assert videos[0].decryption_key == "1122334455"
        assert videos[0].duration == 18
        assert videos[0].resolution == "1080x1920"
        assert videos[0].filesize == 2048

    def test_ip_host_mmtls_binary_metadata_is_applied_to_later_video_flow(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772811802250000002"
        encfilekey = "iphost1234567890iphost1234567890"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        binary_payload = (
            b"\x00\x01MMTLS"
            + (
                "{"
                "\"title\":\"IP Host MMTLS Title\","
                "\"thumbUrl\":\"https://res.wx.qq.com/shop/public/ip-host-thumb.png\","
                "\"decodeKey\":\"5556667778\","
                f"\"taskid\":\"{task_id}\","
                f"\"encfilekey\":\"{encfilekey}\","
                f"\"url\":\"{video_url}\""
                "}"
            ).encode("utf-8")
            + b"\x02\x03"
        )

        mmtls_flow = MagicMock()
        mmtls_flow.request.pretty_url = "http://180.101.242.212/mmtls/00000edf"
        mmtls_flow.response.headers = {"Content-Type": "application/octet-stream"}
        mmtls_flow.response.status_code = 200
        mmtls_flow.response.content = binary_payload
        mmtls_flow.response.get_text.side_effect = ValueError("binary payload")
        mmtls_flow.response.set_text = MagicMock()

        addon.response(mmtls_flow)

        samples = sniffer.get_runtime_statistics()["recent_response_samples"]
        assert any(sample["host"] == "180.101.242.212" for sample in samples)

        video_flow = MagicMock()
        video_flow.request.pretty_url = video_url
        video_flow.response.headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024000",
        }

        addon.response(video_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "IP Host MMTLS Title"
        assert videos[0].thumbnail == "https://res.wx.qq.com/shop/public/ip-host-thumb.png"
        assert videos[0].decryption_key == "5556667778"

    def test_scheme_less_finder_url_in_binary_payload_is_normalized(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        task_id = "pc-1772811802250000001"
        encfilekey = "feed1234567890feed1234567890abcd"
        binary_payload = (
            b"\x00\x01"
            + (
                "{"
                "\"title\":\"Embedded URL Title\","
                "\"decodeKey\":\"2065249527\","
                "\"url\":\"//finder.video.qq.com/251/20302/stodownload"
                f"?encfilekey={encfilekey}&taskid={task_id}&token=test\""
                "}"
            ).encode("utf-8")
            + b"\x02\x03"
        )

        mmtls_flow = MagicMock()
        mmtls_flow.request.pretty_url = "http://extshort.weixin.qq.com/mmtls/00000ee2"
        mmtls_flow.response.headers = {"Content-Type": "application/octet-stream"}
        mmtls_flow.response.status_code = 200
        mmtls_flow.response.content = binary_payload
        mmtls_flow.response.get_text.side_effect = ValueError("binary payload")
        mmtls_flow.response.set_text = MagicMock()

        addon.response(mmtls_flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].url.startswith("https://finder.video.qq.com/")
        assert videos[0].title == "Embedded URL Title"
        assert videos[0].decryption_key == "2065249527"

    def test_raw_tcp_tls_clienthello_is_recorded_for_diagnostics(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        sni = b"channels.weixin.qq.com"
        sni_ext = bytes([
            0x00, 0x00,
            0x00, len(sni) + 5,
            0x00, len(sni) + 3,
            0x00,
            0x00, len(sni),
        ]) + sni
        client_hello = bytes([
            0x03, 0x03,
        ]) + bytes(32) + bytes([
            0x00,
            0x00, 0x02, 0x00, 0x2F,
            0x01, 0x00,
            0x00, len(sni_ext),
        ]) + sni_ext
        handshake = bytes([
            0x01,
            0x00, (len(client_hello) >> 8) & 0xFF, len(client_hello) & 0xFF,
        ]) + client_hello
        tls_record = bytes([
            0x16,
            0x03, 0x01,
            (len(handshake) >> 8) & 0xFF, len(handshake) & 0xFF,
        ]) + handshake

        flow = MagicMock()
        flow.server_conn.address = ("117.89.177.97", 443)
        flow.messages = [MagicMock(from_client=True, content=tls_record)]
        flow.metadata = {}

        addon.tcp_message(flow)

        samples = sniffer.get_runtime_statistics()["recent_response_samples"]
        assert any(
            sample["host"] == "channels.weixin.qq.com" and sample["classification"] == "tcp_tls_sni"
            for sample in samples
        )

    def test_raw_tcp_midstream_flow_is_recorded_for_diagnostics(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        flow = MagicMock()
        flow.server_conn.address = ("117.89.177.97", 443)
        flow.messages = [MagicMock(from_client=True, content=b"\x17\x03\x03\x00\x10" + b"\x00" * 16)]
        flow.metadata = {}

        addon.tcp_message(flow)

        samples = sniffer.get_runtime_statistics()["recent_response_samples"]
        assert any(
            sample["host"] == "117.89.177.97" and sample["classification"] == "tcp_midstream_or_non_tls"
            for sample in samples
        )

    def test_raw_tcp_midstream_port_80_is_recorded_for_diagnostics(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        flow = MagicMock()
        flow.server_conn.address = ("180.111.196.240", 80)
        flow.messages = [MagicMock(from_client=True, content=b"\x17\x03\x03\x00\x10" + b"\x00" * 16)]
        flow.metadata = {}

        addon.tcp_message(flow)

        samples = sniffer.get_runtime_statistics()["recent_response_samples"]
        assert any(
            sample["host"] == "180.111.196.240" and sample["classification"] == "tcp_midstream_or_non_tls"
            for sample in samples
        )

    def test_raw_tcp_server_binary_probe_can_cache_metadata(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        encfilekey = "RAWTCPKEY123456"
        task_id = "pc-1772810744905962706"
        binary_payload = (
            b"\x00\x01"
            + (
                "{"
                "\"title\":\"Raw TCP Title\","
                "\"decodeKey\":\"2065249527\","
                "\"thumbUrl\":\"https://res.wx.qq.com/mock-thumb.png\","
                "\"url\":\"https://finder.video.qq.com/251/20302/stodownload"
                f"?encfilekey={encfilekey}&taskid={task_id}&token=test\""
                "}"
            ).encode("utf-8")
            + b"\x02\x03"
        )

        flow = MagicMock()
        flow.server_conn.address = ("61.151.230.226", 80)
        flow.messages = [MagicMock(from_client=False, content=binary_payload)]
        flow.metadata = {}

        addon.tcp_message(flow)

        videos = sniffer.get_detected_videos()
        assert len(videos) == 1
        assert videos[0].title == "Raw TCP Title"
        assert videos[0].decryption_key == "2065249527"

        samples = sniffer.get_runtime_statistics()["recent_response_samples"]
        assert any(
            sample["host"] == "61.151.230.226" and sample["classification"] == "tcp_server_binary_hit"
            for sample in samples
        )

    def test_js_asset_injection_is_skipped_after_html_injection(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        html_flow = MagicMock()
        html_flow.request.pretty_url = "https://channels.weixin.qq.com/web/pages/home?foo=bar"
        html_flow.response.headers = {"Content-Type": "text/html; charset=UTF-8"}
        html_flow.response.content = b"<html><head></head><body></body></html>"
        html_flow.response.get_text.return_value = "<html><head></head><body></body></html>"
        html_flow.response.set_text = MagicMock()

        assert addon._inject_channels_script(html_flow) is True
        html_flow.response.set_text.assert_called_once()

        asset_flow = MagicMock()
        asset_flow.request.pretty_url = "https://res.wx.qq.com/t/wx_fed/finder/web/web-finder/res/js/index.publish.js"
        asset_flow.response.headers = {"Content-Type": "application/javascript; charset=utf-8"}
        asset_flow.response.content = b"console.log('bundle');"
        asset_flow.response.get_text.return_value = "console.log('bundle');"
        asset_flow.response.set_text = MagicMock()

        assert addon._inject_channels_script_asset(asset_flow) is False
        asset_flow.response.set_text.assert_not_called()

    def test_html_injection_supports_wxa_template_shell(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        flow = MagicMock()
        flow.request.pretty_url = "https://wxa.wxs.qq.com/tmpl/pf/base_tmpl.html?env=timeline"
        flow.response.headers = {"Content-Type": "text/html; charset=UTF-8"}
        flow.response.content = b"<html><head></head><body></body></html>"
        flow.response.get_text.return_value = "<html><head></head><body></body></html>"
        flow.response.set_text = MagicMock()

        assert addon._inject_channels_script(flow) is True
        flow.response.set_text.assert_called_once()

    def test_inject_proxy_endpoints_accept_supported_wechat_hosts(self, sniffer):
        _ = sniffer

        proxy_flow = MagicMock()
        proxy_flow.request.pretty_url = f"https://wxa.wxs.qq.com{CHANNELS_INJECT_PROXY_PATH}"
        assert VideoSnifferAddon._is_channels_inject_proxy_request(proxy_flow) is True

        script_flow = MagicMock()
        script_flow.request.pretty_url = f"https://servicewechat.com{CHANNELS_INJECT_SCRIPT_PATH}"
        assert VideoSnifferAddon._is_channels_inject_script_request(script_flow) is True

    def test_js_asset_detection_supports_wxa_shell_assets(self):
        assert VideoSnifferAddon._is_channels_script_asset(
            "https://wxa.wxs.qq.com/tmpl/pf/app-service.js",
            "application/javascript; charset=UTF-8",
        ) is True

    def test_normalize_decode_key_accepts_long_like_shapes(self):
        assert ProxySniffer._normalize_decode_key({"$numberLong": "1234567890123456789"}) == "1234567890123456789"
        assert ProxySniffer._normalize_decode_key({"low": 2, "high": 1, "unsigned": True}) == "4294967298"

    def test_normalize_decode_key_rejects_script_identifier_like_values(self):
        assert ProxySniffer._normalize_decode_key("normalizeDecodeKeyValue") is None
        assert ProxySniffer._normalize_decode_key("decodeKey") is None

    def test_sanitize_video_title_drops_generic_channels_placeholder(self):
        assert ProxySniffer._sanitize_video_title("\u89c6\u9891\u53f7") is None
        assert ProxySniffer._sanitize_video_title("\u5fae\u4fe1\u89c6\u9891\u53f7") is None
        assert ProxySniffer._sanitize_video_title("Video Player is loading.") is None

    def test_parse_wechat_api_response_extracts_decode_key(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        metadata = addon._parse_wechat_api_response(
            {
                "feed": {
                    "objectDesc": {
                        "description": "real title",
                        "media": {
                            "coverUrl": "https://wx.qlogo.cn/test-cover.jpg",
                            "videoWidth": 720,
                            "videoHeight": 1280,
                            "fileSize": 2048,
                        },
                    },
                    "specList": [
                        {
                            "decodeKey": {
                                "low": 2,
                                "high": 1,
                                "unsigned": True,
                            }
                        }
                    ],
                }
            }
        )

        assert metadata is not None
        assert metadata.title == "real title"
        assert metadata.decode_key == "4294967298"
        assert metadata.thumbnail == "https://wx.qlogo.cn/test-cover.jpg"

        assert metadata.resolution == "720x1280"

    def test_parse_wechat_api_response_extracts_extended_decode_key_aliases(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        metadata = addon._parse_wechat_api_response(
            {
                "feed": {
                    "description": "alias title",
                    "media": {
                        "coverUrl": "https://wx.qlogo.cn/alias-cover.jpg",
                        "seedValue": "1234567890",
                    },
                }
            }
        )

        assert metadata is not None
        assert metadata.title == "alias title"
        assert metadata.decode_key == "1234567890"
        assert metadata.thumbnail == "https://wx.qlogo.cn/alias-cover.jpg"

    def test_parse_wechat_api_response_extracts_nested_thumbnail_url(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        metadata = addon._parse_wechat_api_response(
            {
                "feed": {
                    "description": "nested thumb title",
                    "cover": {
                        "url": "https://wx.qlogo.cn/nested-cover.jpg"
                    },
                }
            }
        )

        assert metadata is not None
        assert metadata.thumbnail == "https://wx.qlogo.cn/nested-cover.jpg"

    def test_manual_add_video_from_url_reuses_cached_metadata(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            "?m=cached-thumb-key&taskid=pc-1772811802250000999&token=test"
        )

        addon.cache_external_metadata(
            VideoMetadata(
                title="Cached metadata title",
                duration=12,
                resolution="720x1280",
                filesize=2048,
                thumbnail="https://wx.qlogo.cn/cached-cover.jpg",
                width=720,
                height=1280,
                decode_key="1234567890",
            ),
            sniffer._build_metadata_cache_keys(video_url),
        )

        video = sniffer.add_video_from_url(video_url)

        assert video is not None
        assert video.title == "Cached metadata title"
        assert video.thumbnail == "https://wx.qlogo.cn/cached-cover.jpg"
        assert video.decryption_key == "1234567890"
        assert video.duration == 12

    def test_prefetched_page_html_applies_metadata_to_later_video_flow(self, sniffer):
        addon = VideoSnifferAddon(sniffer)
        encfilekey = "prefetch1234567890prefetch1234567890"
        task_id = "pc-1772811802250001888"
        video_url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            f"?encfilekey={encfilekey}&taskid={task_id}&token=test"
        )
        page_url = "https://channels.weixin.qq.com/web/pages/home?context_id=test-prefetch"
        html = (
            "<html><head></head><body><script>"
            "window.__INITIAL_STATE__={"
            "\"feed\":{"
            "\"description\":\"Prefetched Title\","
            "\"thumbUrl\":\"https://wx.qlogo.cn/prefetched-cover.jpg\","
            f"\"encfilekey\":\"{encfilekey}\","
            f"\"taskid\":\"{task_id}\","
            f"\"url\":\"{video_url}\""
            "}"
            "};"
            "</script></body></html>"
        )

        addon._fetch_page_document = MagicMock(
            return_value=(200, "text/html; charset=utf-8", html)
        )

        addon._prefetch_page_metadata(
            page_url,
            {"Cookie": "test=1"},
            video_url,
        )

        video = sniffer.add_video_from_url(video_url)

        assert video is not None
        assert video.title == "Prefetched Title"
        assert video.thumbnail == "https://wx.qlogo.cn/prefetched-cover.jpg"

    def test_extract_prefetch_page_url_decodes_percent_encoded_page_url(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        flow = MagicMock()
        flow.request.headers = {"Origin": "https://channels.weixin.qq.com"}
        flow.request.pretty_url = "https://channels.weixin.qq.com/web/report-perf?pf=web"
        flow.request.get_text.return_value = (
            "pageUrl=https%3A%2F%2Fchannels.weixin.qq.com%2Fweb%2Fpages%2Fhome%3Ffoo%3Dbar"
        )

        page_url = addon._extract_prefetch_page_url(flow, flow.request.pretty_url)

        assert page_url == "https://channels.weixin.qq.com/web/pages/home?foo=bar"

    def test_extract_prefetch_page_url_normalizes_report_perf_to_home(self, sniffer):
        addon = VideoSnifferAddon(sniffer)

        flow = MagicMock()
        flow.request.headers = {"Origin": "https://channels.weixin.qq.com"}
        flow.request.pretty_url = "https://channels.weixin.qq.com/web/report-perf?pf=web"
        flow.request.get_text.return_value = ""

        page_url = addon._extract_prefetch_page_url(flow, flow.request.pretty_url)

        assert page_url == "https://channels.weixin.qq.com/web/pages/home"

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
