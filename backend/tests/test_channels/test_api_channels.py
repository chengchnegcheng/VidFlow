"""
视频号 API 端点测试

测试各端点的请求/响应格式和错误处理。
Validates: Requirements 8.1, 8.2
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import tempfile
from pathlib import Path

from src.core.channels.proxy_sniffer import ProxySniffer, VideoSnifferAddon
from src.core.channels.models import DetectedVideo, EncryptionType, ProxyInfo, ProxyMode, ProxyType


# ============================================================================
# Test API Models and Logic (without full app)
# ============================================================================

class TestAPIModels:
    """API 模型测试"""

    def test_sniffer_start_response_model(self):
        """测试启动响应模型"""
        from src.api.channels import SnifferStartResponse

        response = SnifferStartResponse(
            success=True,
            proxy_address="127.0.0.1:8888"
        )

        assert response.success is True
        assert response.proxy_address == "127.0.0.1:8888"

    def test_sniffer_status_response_model(self):
        """测试状态响应模型"""
        from src.api.channels import SnifferStatusResponse

        response = SnifferStatusResponse(
            state="running",
            proxy_address="127.0.0.1:8888",
            proxy_port=8888,
            videos_detected=5,
        )

        assert response.state == "running"
        assert response.videos_detected == 5

    def test_detected_video_response_model(self):
        """测试视频响应模型"""
        from src.api.channels import DetectedVideoResponse

        response = DetectedVideoResponse(
            id="test-1",
            url="https://finder.video.qq.com/video.mp4",
            title="Test Video",
            detected_at="2024-01-01T12:00:00",
            encryption_type="none",
        )

        assert response.id == "test-1"
        assert response.title == "Test Video"

    def test_download_request_model(self):
        """测试下载请求模型"""
        from src.api.channels import DownloadRequest

        request = DownloadRequest(
            url="https://finder.video.qq.com/video.mp4",
            quality="best",
        )

        assert request.url == "https://finder.video.qq.com/video.mp4"
        assert request.quality == "best"

    def test_download_response_model(self):
        """测试下载响应模型"""
        from src.api.channels import DownloadResponse

        response = DownloadResponse(
            success=True,
            file_path="/tmp/video.mp4",
            file_size=1024000,
        )

        assert response.success is True
        assert response.file_size == 1024000

    def test_cert_info_response_model(self):
        """测试证书信息响应模型"""
        from src.api.channels import CertInfoResponse

        response = CertInfoResponse(
            exists=True,
            valid=True,
            fingerprint="AA:BB:CC:DD",
        )

        assert response.exists is True
        assert response.valid is True

    def test_config_response_model(self):
        """测试配置响应模型"""
        from src.api.channels import ConfigResponse

        response = ConfigResponse(
            proxy_port=8888,
            download_dir="/tmp/downloads",
            auto_decrypt=True,
            quality_preference="best",
            clear_on_exit=False,
        )

        assert response.proxy_port == 8888
        assert response.auto_decrypt is True

    def test_config_update_request_model(self):
        """测试配置更新请求模型"""
        from src.api.channels import ConfigUpdateRequest

        request = ConfigUpdateRequest(
            proxy_port=9999,
            auto_decrypt=False,
        )

        assert request.proxy_port == 9999
        assert request.auto_decrypt is False


# ============================================================================
# Test Helper Functions
# ============================================================================

class TestHelperFunctions:
    """辅助函数测试"""

    def test_get_sniffer_creates_instance(self):
        """get_sniffer 应该创建实例（使用同步版本）"""
        from src.api import channels

        # 重置全局状态
        channels._sniffer = None

        with patch.object(channels, 'get_data_dir', return_value=Path(tempfile.gettempdir())):
            # 使用同步版本创建 sniffer 实例
            cert_dir = Path(tempfile.gettempdir()) / "channels" / "certs"
            channels._sniffer = ProxySniffer(port=channels._config.proxy_port, cert_dir=cert_dir)
            sniffer = channels.get_sniffer_sync()
            assert sniffer is not None
            assert sniffer.port == channels._config.proxy_port

    def test_get_cert_manager_creates_instance(self):
        """get_cert_manager 应该创建实例"""
        from src.api import channels

        # 重置全局状态
        channels._cert_manager = None

        with patch.object(channels, 'get_data_dir', return_value=Path(tempfile.gettempdir())):
            cert_manager = channels.get_cert_manager()
            assert cert_manager is not None

    def test_get_downloader_creates_instance(self):
        """get_downloader 应该创建实例"""
        from src.api import channels

        # 重置全局状态
        channels._downloader = None

        downloader = channels.get_downloader()
        assert downloader is not None
        assert downloader.platform_name == "weixin_channels"

    def test_prepare_display_videos_sanitizes_noise_and_merges_duplicates(self):
        """API 返回前应清洗脏标题，并把同一视频的重复占位项合并。"""
        from src.api import channels

        sniffer = ProxySniffer(
            port=18888,
            cert_dir=Path(tempfile.gettempdir()) / "channels" / "api-helper-tests",
        )
        url = (
            "https://finder.video.qq.com/251/20302/stodownload"
            "?encfilekey=abc123def4567890abc123def4567890&taskid=pc-1773234544446000000"
        )
        now = datetime.now()
        videos = [
            DetectedVideo(
                id="legacy-noise",
                url=url,
                title="IE=edge",
                thumbnail="https://wx.qlogo.cn/cover.jpg",
                detected_at=now,
                encryption_type=EncryptionType.UNKNOWN,
                decryption_key=None,
            ),
            DetectedVideo(
                id="legacy-dup",
                url=url,
                title="channels_177323454444",
                detected_at=now,
                encryption_type=EncryptionType.ISAAC64,
                decryption_key="1234567890",
            ),
        ]

        prepared = channels._prepare_display_videos(sniffer, videos)

        assert len(prepared) == 1
        assert prepared[0].title != "IE=edge"
        assert prepared[0].title.startswith("channels_")
        assert prepared[0].thumbnail == "https://wx.qlogo.cn/cover.jpg"
        assert prepared[0].decryption_key == "1234567890"
        assert prepared[0].encryption_type == EncryptionType.ISAAC64

    def test_prepare_display_videos_merges_rotating_channels_urls_by_metadata_fingerprint(self):
        """Different channels URLs for the same video should collapse into one visible item."""
        from src.api import channels

        sniffer = ProxySniffer(
            port=18889,
            cert_dir=Path(tempfile.gettempdir()) / "channels" / "api-helper-tests-identity",
        )
        now = datetime.now()
        videos = [
            DetectedVideo(
                id="rotating-a",
                url=(
                    "https://finder.video.qq.com/251/20302/stodownload"
                    "?encfilekey=abc123def4567890abc123def4567890&taskid=pc-1773723506865923188"
                ),
                title="测试视频标题-旋转画质合并",
                duration=37,
                resolution="720x1280",
                thumbnail="https://finder.video.qq.com/251/20304/stodownload?idx=1&picformat=200",
                detected_at=now,
                encryption_type=EncryptionType.ISAAC64,
                decryption_key=None,
            ),
            DetectedVideo(
                id="rotating-b",
                url=(
                    "https://finder.video.qq.com/251/20302/stodownload"
                    "?encfilekey=zzz999yyy888777666555444333222111&taskid=pc-1773723506865439019"
                ),
                title="测试视频标题-旋转画质合并",
                duration=37,
                resolution="720x1280",
                thumbnail="https://finder.video.qq.com/251/20304/stodownload?idx=1&picformat=200",
                detected_at=now,
                encryption_type=EncryptionType.ISAAC64,
                decryption_key="1234567890",
            ),
        ]

        prepared = channels._prepare_display_videos(sniffer, videos)

        assert len(prepared) == 1
        assert prepared[0].title == "测试视频标题-旋转画质合并"
        assert prepared[0].decryption_key == "1234567890"

    def test_prepare_display_videos_ignores_filesize_noise_and_prefers_keyed_url(self):
        """Visible items should merge even when rotating channels URLs report different sizes."""
        from src.api import channels

        sniffer = ProxySniffer(
            port=18890,
            cert_dir=Path(tempfile.gettempdir()) / "channels" / "api-helper-tests-filesize",
        )
        now = datetime.now()
        url_without_key = (
            "https://finder.video.qq.com/251/20302/stodownload"
            "?encfilekey=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa111111"
            "&taskid=pc-1773729783910169001"
        )
        url_with_key = (
            "https://finder.video.qq.com/251/20302/stodownload"
            "?encfilekey=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa222222"
            "&taskid=pc-1773729783910169002"
        )
        videos = [
            DetectedVideo(
                id="rotating-size-a",
                url=url_without_key,
                title="测试视频标题-旋转画质合并",
                duration=13,
                resolution="1080x1920",
                filesize=953677,
                thumbnail="https://finder.video.qq.com/251/20304/stodownload?idx=1&picformat=200",
                detected_at=now,
                encryption_type=EncryptionType.ISAAC64,
                decryption_key=None,
            ),
            DetectedVideo(
                id="rotating-size-b",
                url=url_with_key,
                title="测试视频标题-旋转画质合并",
                duration=13,
                resolution="1080x1920",
                filesize=880933,
                thumbnail="https://finder.video.qq.com/251/20304/stodownload?idx=1&picformat=200",
                detected_at=now,
                encryption_type=EncryptionType.ISAAC64,
                decryption_key="1234567890",
            ),
        ]

        prepared = channels._prepare_display_videos(sniffer, videos)

        assert len(prepared) == 1
        assert prepared[0].decryption_key == "1234567890"
        assert prepared[0].url == url_with_key

    def test_prepare_display_videos_merges_same_thumbnail_even_when_resolution_differs(self):
        """Visible items should collapse when rotating URLs disagree on resolution but share title/thumb/duration."""
        from src.api import channels

        sniffer = ProxySniffer(
            port=18892,
            cert_dir=Path(tempfile.gettempdir()) / "channels" / "api-helper-tests-resolution",
        )
        now = datetime.now()
        shared_thumbnail = "https://wx.qlogo.cn/finderhead/ver_1/shared-thumb/132"
        videos = [
            DetectedVideo(
                id="rotating-resolution-a",
                url=(
                    "https://finder.video.qq.com/251/20350/stodownload"
                    "?encfilekey=cccccccccccccccccccccccccccccccccccc111111"
                    "&taskid=pc-1773810655869207586"
                ),
                title="测试视频标题-旋转画质合并",
                duration=20,
                resolution="576x1024",
                thumbnail=shared_thumbnail,
                detected_at=now,
                encryption_type=EncryptionType.ISAAC64,
                decryption_key=None,
            ),
            DetectedVideo(
                id="rotating-resolution-b",
                url=(
                    "https://finder.video.qq.com/251/20302/stodownload"
                    "?encfilekey=cccccccccccccccccccccccccccccccccccc222222"
                    "&taskid=pc-1773810655870532189"
                ),
                title="测试视频标题-旋转画质合并",
                duration=20,
                resolution=None,
                thumbnail=shared_thumbnail,
                detected_at=now,
                encryption_type=EncryptionType.ISAAC64,
                decryption_key=None,
            ),
        ]

        prepared = channels._prepare_display_videos(sniffer, videos)

        assert len(prepared) == 1
        assert prepared[0].title == "测试视频标题-旋转画质合并"
        assert prepared[0].thumbnail == shared_thumbnail

    def test_prepare_display_videos_merges_same_thumbnail_when_sibling_missing_duration(self):
        """Visible items should collapse when one rotating URL lacks duration/resolution but shares title/thumb."""
        from src.api import channels

        sniffer = ProxySniffer(
            port=18893,
            cert_dir=Path(tempfile.gettempdir()) / "channels" / "api-helper-tests-missing-duration",
        )
        now = datetime.now()
        shared_thumbnail = "https://wx.qlogo.cn/finderhead/ver_1/shared-thumb/132"
        videos = [
            DetectedVideo(
                id="rotating-duration-a",
                url=(
                    "https://finder.video.qq.com/251/20350/stodownload"
                    "?encfilekey=dddddddddddddddddddddddddddddddddddd111111"
                    "&taskid=pc-1773810655869207586"
                ),
                title="测试视频标题-旋转画质合并",
                duration=13,
                resolution="1080x1648",
                filesize=0,
                thumbnail=shared_thumbnail,
                detected_at=now,
                encryption_type=EncryptionType.ISAAC64,
                decryption_key=None,
            ),
            DetectedVideo(
                id="rotating-duration-b",
                url=(
                    "https://finder.video.qq.com/251/20302/stodownload"
                    "?encfilekey=dddddddddddddddddddddddddddddddddddd222222"
                    "&taskid=pc-1773810655870532189"
                ),
                title="测试视频标题-旋转画质合并",
                duration=None,
                resolution=None,
                filesize=14,
                thumbnail=shared_thumbnail,
                detected_at=now,
                encryption_type=EncryptionType.ISAAC64,
                decryption_key=None,
            ),
        ]

        prepared = channels._prepare_display_videos(sniffer, videos)

        assert len(prepared) == 1
        assert prepared[0].title == "测试视频标题-旋转画质合并"
        assert prepared[0].thumbnail == shared_thumbnail

    def test_resolve_detected_video_can_reuse_cached_decode_key_for_rotating_url(self):
        """Download resolution should reuse cached decodeKey for sibling rotating URLs."""
        from src.api import channels

        sniffer = ProxySniffer(
            port=18891,
            cert_dir=Path(tempfile.gettempdir()) / "channels" / "api-helper-tests-resolve",
        )
        _addon = VideoSnifferAddon(sniffer)
        url_without_key = (
            "https://finder.video.qq.com/251/20302/stodownload"
            "?encfilekey=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb111111"
            "&taskid=pc-1773729783910169101"
        )
        url_with_key = (
            "https://finder.video.qq.com/251/20302/stodownload"
            "?encfilekey=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb222222"
            "&taskid=pc-1773729783910169102"
        )

        sniffer.add_detected_video(
            DetectedVideo(
                id="raw-without-key",
                url=url_without_key,
                title="测试视频标题-旋转画质合并",
                duration=13,
                resolution="1080x1920",
                thumbnail="https://finder.video.qq.com/251/20304/stodownload?idx=1&picformat=200",
                detected_at=datetime.now(),
                encryption_type=EncryptionType.ISAAC64,
                decryption_key=None,
            )
        )

        sniffer.ingest_injected_video(
            url=url_with_key,
            title="测试视频标题-旋转画质合并",
            thumbnail="https://finder.video.qq.com/251/20304/stodownload?idx=1&picformat=200",
            duration=13,
            width=1080,
            height=1920,
            decode_key="1234567890",
        )

        with patch.object(channels, "get_sniffer", return_value=sniffer):
            resolved = channels._resolve_detected_video(url_without_key)

        assert resolved is not None
        assert resolved.decryption_key == "1234567890"

    def test_prepare_download_task_payloads_hides_duplicate_channel_tasks(self):
        """The download task list should only show the newest task for the same video."""
        from src.api import channels
        from src.models.download import DownloadTask

        newer_task = DownloadTask(
            task_id="channels_new",
            url=(
                "https://finder.video.qq.com/251/20302/stodownload"
                "?encfilekey=abc123def4567890abc123def4567890"
            ),
            title="测试视频标题-旋转画质合并",
            platform="weixin_channels",
            thumbnail="https://finder.video.qq.com/251/20304/stodownload?idx=1&picformat=200",
            duration=37,
            status="encrypted",
            progress=100.0,
            filename=str(Path(tempfile.gettempdir()) / "video.mp4.encrypted"),
            filesize=893344,
            error_message="Video payload is still encrypted.",
        )
        newer_task.created_at = datetime(2026, 3, 17, 13, 1, 0)

        older_task = DownloadTask(
            task_id="channels_old",
            url=(
                "https://finder.video.qq.com/251/20302/stodownload"
                "?encfilekey=zzz999yyy888777666555444333222111"
            ),
            title="测试视频标题-旋转画质合并",
            platform="weixin_channels",
            thumbnail="https://finder.video.qq.com/251/20304/stodownload?idx=1&picformat=200",
            duration=37,
            status="completed",
            progress=100.0,
            filename=str(Path(tempfile.gettempdir()) / "video.mp4"),
            filesize=893344,
            error_message=None,
        )
        older_task.created_at = datetime(2026, 3, 17, 12, 59, 0)

        prepared = channels._prepare_download_task_payloads([newer_task, older_task])

        assert len(prepared) == 1
        assert prepared[0]["task_id"] == "channels_new"
        assert prepared[0]["status"] == "encrypted"

    def test_auto_prepare_wechat_channels_cache_clears_profiles_dir(self, monkeypatch):
        """Starting channels capture should be able to clear stale WeChat web profiles automatically."""
        from src.api import channels

        cache_dir = Path(tempfile.gettempdir()) / "channels-cache-cleanup-test"
        nested_dir = cache_dir / "Default"
        nested_dir.mkdir(parents=True, exist_ok=True)
        (nested_dir / "Preferences").write_text("{}", encoding="utf-8")
        (cache_dir / "lockfile").write_text("1", encoding="utf-8")

        class DummySniffer:
            def _recycle_wechat_renderer_processes(self, force_helpers: bool = False):
                assert force_helpers is True
                return ["WeChatAppEx.exe:1234"]

        monkeypatch.setattr(channels, "_get_wechat_channels_cache_dir", lambda: cache_dir)
        monkeypatch.setitem(channels._runtime_config, "auto_clean_wechat_cache", True)

        result = channels._auto_prepare_wechat_channels_cache(DummySniffer())

        assert result["removed_entries"] == 2
        assert result["recycled_renderers"] == ["WeChatAppEx.exe:1234"]
        assert "已自动清理微信视频号缓存" in result["message"]
        assert list(cache_dir.iterdir()) == []


# ============================================================================
# Test Config Management
# ============================================================================

class TestConfigManagement:
    """配置管理测试"""

    def test_default_config(self):
        """默认配置值"""
        from src.api.channels import _config

        assert _config.proxy_port == 8888
        assert _config.auto_decrypt is True
        assert _config.auto_clean_wechat_cache is True
        assert _config.quality_preference == "best"

    def test_config_to_dict(self):
        """配置转换为字典"""
        from src.core.channels.models import ChannelsConfig

        config = ChannelsConfig(
            proxy_port=9999,
            download_dir="/custom/path",
            auto_decrypt=False,
        )

        d = config.to_dict()

        assert d["proxy_port"] == 9999
        assert d["download_dir"] == "/custom/path"
        assert d["auto_decrypt"] is False


# ============================================================================
# Integration-like Tests (with mocked dependencies)
# ============================================================================

class TestAPIIntegration:
    """API 集成测试（使用 mock）"""

    def test_sniffer_status_conversion(self):
        """嗅探器状态转换"""
        from src.core.channels.models import SnifferState, SnifferStatus
        from src.api.channels import SnifferStatusResponse

        status = SnifferStatus(
            state=SnifferState.RUNNING,
            proxy_address="127.0.0.1:8888",
            proxy_port=8888,
            videos_detected=3,
            started_at=datetime(2024, 1, 1, 12, 0, 0),
        )

        response = SnifferStatusResponse(
            state=status.state.value,
            proxy_address=status.proxy_address,
            proxy_port=status.proxy_port,
            videos_detected=status.videos_detected,
            started_at=status.started_at.isoformat() if status.started_at else None,
            error_message=status.error_message,
        )

        assert response.state == "running"
        assert response.videos_detected == 3

    def test_detected_video_conversion(self):
        """检测到的视频转换"""
        from src.core.channels.models import DetectedVideo, EncryptionType
        from src.api.channels import DetectedVideoResponse

        video = DetectedVideo(
            id="test-1",
            url="https://finder.video.qq.com/video.mp4",
            title="Test Video",
            duration=120,
            detected_at=datetime(2024, 1, 1, 12, 0, 0),
            encryption_type=EncryptionType.XOR,
        )

        response = DetectedVideoResponse(
            id=video.id,
            url=video.url,
            title=video.title,
            duration=video.duration,
            detected_at=video.detected_at.isoformat(),
            encryption_type=video.encryption_type.value,
        )

        assert response.id == "test-1"
        assert response.encryption_type == "xor"

    def test_cert_info_conversion(self):
        """证书信息转换"""
        from src.core.channels.models import CertInfo
        from src.api.channels import CertInfoResponse

        info = CertInfo(
            exists=True,
            valid=True,
            expires_at=datetime(2027, 1, 1),
            fingerprint="AA:BB:CC:DD",
            path="/tmp/cert.pem",
        )

        response = CertInfoResponse(
            exists=info.exists,
            valid=info.valid,
            expires_at=info.expires_at.isoformat() if info.expires_at else None,
            fingerprint=info.fingerprint,
            path=info.path,
        )

        assert response.exists is True
        assert response.valid is True
        assert "2027" in response.expires_at


class TestChannelsDownloadGuard:
    """涓嬭浇淇濇姢閫昏緫娴嬭瘯"""

    @pytest.mark.asyncio
    async def test_download_video_allows_encrypted_payload_without_decode_key(self, monkeypatch):
        """鍔犲瘑瑙嗛鍙疯祫婧愮己灏?decodeKey 鏃跺簲鐩存帴鎷掔粷涓嬭浇"""
        from src.api import channels

        request = channels.DownloadRequest(
            url="https://finder.video.qq.com/251/20302/stodownload?encfilekey=Cvvj5Ix3eez3Y79S",
            quality="best",
            auto_decrypt=False,
            decryption_key=None,
        )

        detected_video = DetectedVideo(
            id="test-video",
            url=request.url,
            title="channels_177279598807",
            detected_at=datetime.now(),
            encryption_type=EncryptionType.ISAAC64,
            decryption_key=None,
            thumbnail=None,
        )

        monkeypatch.setattr(channels, "_resolve_detected_video", lambda _: detected_video)
        monkeypatch.setattr(channels, "_resolve_task_title", lambda _: "channels_177279598807")
        monkeypatch.setattr(
            channels,
            "_resolve_download_output_path",
            lambda normalized_url, task_title, preferred_output_path: str(
                Path(tempfile.gettempdir()) / "channels_177279598807.mp4"
            ),
        )
        monkeypatch.setattr(channels, "_attach_download_task_callback", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(channels, "_download_tasks", {})

        class DummySession:
            def add(self, _task):
                return None

            async def commit(self):
                return None

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class DummyDownloader:
            output_dir = Path(tempfile.gettempdir())

        async def fake_run_download_task(*_args, **_kwargs):
            return None

        monkeypatch.setattr(channels, "AsyncSessionLocal", lambda: DummySession())
        monkeypatch.setattr(channels, "get_downloader", lambda: DummyDownloader())
        monkeypatch.setattr(channels, "_run_download_task", fake_run_download_task)

        response = await channels.download_video(request)

        assert response["success"] is True
        assert response["task_id"].startswith("channels_")
        assert response["message"] == "下载任务已创建"

        created_task = channels._download_tasks[response["task_id"]]
        await created_task

    @pytest.mark.asyncio
    async def test_run_download_task_marks_encrypted_payloads_with_encrypted_status(self, monkeypatch):
        """Encrypted payloads without a usable decodeKey should not be reported as completed MP4 downloads."""
        from src.api import channels

        updates = []

        async def fake_update_download_task(task_id, **kwargs):
            updates.append((task_id, kwargs))
            return None

        class DummyDownloader:
            async def download_video(self, **_kwargs):
                return {
                    "success": True,
                    "file_path": str(Path(tempfile.gettempdir()) / "channels_test.mp4.encrypted"),
                    "file_size": 893344,
                    "encrypted": True,
                    "decrypted": False,
                    "decrypt_hint": "Video payload is still encrypted.",
                }

        monkeypatch.setattr(channels, "_update_download_task", fake_update_download_task)
        monkeypatch.setattr(channels, "get_downloader", lambda: DummyDownloader())

        await channels._run_download_task(
            "channels_task_encrypted",
            url="https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc123def4567890",
            quality="best",
            output_path=str(Path(tempfile.gettempdir()) / "channels_test.mp4"),
            auto_decrypt=False,
            decryption_key=None,
            title="测试视频标题-旋转画质合并",
        )

        assert updates[0][1]["status"] == "downloading"
        assert updates[-1][1]["status"] == "encrypted"
        assert updates[-1][1]["filename"].endswith(".mp4.encrypted")
        assert updates[-1][1]["error_message"] == "Video payload is still encrypted."

    def test_build_video_payload_marks_incomplete_metadata_as_placeholder(self):
        """缂哄皯鏍囬/缂╃暐鍥?瀵嗛挜鐨勮棰戝簲甯﹀崰浣嶆彁绀?"""
        from src.api.channels import _build_video_payload

        video = DetectedVideo(
            id="test-video",
            url="https://finder.video.qq.com/251/20302/stodownload?encfilekey=Cvvj5Ix3eez3Y79S",
            title="channels_177279598807",
            detected_at=datetime.now(),
            encryption_type=EncryptionType.ISAAC64,
            decryption_key=None,
            thumbnail=None,
        )

        payload = _build_video_payload(video)

        assert payload["is_placeholder"] is True
        assert "decodeKey" in payload["placeholder_message"]


class TestProxyEnvironmentWarning:
    """代理环境告警构造测试"""

    def test_build_proxy_environment_warning_for_tun_proxy(self):
        """TUN 代理应返回明确的视频号抓取告警"""
        from src.api.channels import _build_proxy_environment_warning

        warning = _build_proxy_environment_warning(
            ProxyInfo(
                proxy_type=ProxyType.CLASH_VERGE,
                proxy_mode=ProxyMode.TUN,
                process_name="clash-verge.exe",
                is_tun_enabled=True,
            )
        )

        assert warning is not None
        assert "TUN" in warning
        assert "Weixin.exe" in warning
        assert "QQBrowser.exe" in warning
        assert "msedgewebview2.exe" in warning

    def test_build_transparent_start_blocker_for_tun_proxy(self):
        """TUN 代理下应阻止透明嗅探启动，避免 WinDivert 冲突。"""
        from src.api.channels import _build_transparent_start_blocker

        blocker = _build_transparent_start_blocker(
            ProxyInfo(
                proxy_type=ProxyType.CLASH_VERGE,
                proxy_mode=ProxyMode.TUN,
                process_name="clash-verge.exe",
                is_tun_enabled=True,
            )
        )

        assert blocker is not None
        assert blocker["error_code"] == "PROXY_TUN_MODE"
        assert "TUN" in blocker["error_message"]
        assert "WinDivert" in blocker["error_message"]

    def test_resolve_target_processes_defaults_include_wechat_helpers(self):
        """默认透明抓包目标应覆盖微信 4.x 常见辅助浏览器进程。"""
        from src.api.channels import _resolve_target_processes

        resolved = _resolve_target_processes(None)

        assert "Weixin.exe" in resolved
        assert "WeChatAppEx.exe" in resolved
        assert "QQBrowser.exe" in resolved
        assert "msedgewebview2.exe" in resolved

    def test_resolve_target_processes_migrates_previous_helper_default(self):
        from src.api.channels import _resolve_target_processes

        resolved = _resolve_target_processes([
            "Weixin.exe",
            "WeChat.exe",
            "WeChatAppEx.exe",
            "WeChatApp.exe",
            "WeChatBrowser.exe",
            "WeChatPlayer.exe",
            "QQBrowser.exe",
            "msedgewebview2.exe",
        ])

        assert "Weixin.exe" in resolved
        assert "WeChatAppEx.exe" in resolved
        assert "QQBrowser.exe" in resolved
        assert "msedgewebview2.exe" in resolved


class TestProxyEnvironmentWarningSystemProxy:
    def test_build_proxy_environment_warning_for_system_proxy_pac(self):
        from src.api.channels import _build_proxy_environment_warning

        warning = _build_proxy_environment_warning(
            ProxyInfo(
                proxy_type=ProxyType.CLASH_VERGE,
                proxy_mode=ProxyMode.SYSTEM_PROXY,
                process_name="clash-verge.exe",
            )
        )

        assert warning is not None
        assert "PAC" in warning
        assert "WeChatAppEx.exe" in warning
        assert "QQBrowser.exe" in warning


class TestManagedSystemProxyRestore:
    def test_restore_managed_system_proxy_recovers_persisted_vidflow_proxy(self):
        from src.api import channels

        proxy_manager = MagicMock()
        proxy_manager.has_persisted_state.return_value = True
        proxy_manager.is_current_settings_managed.return_value = True
        proxy_manager.restore_proxy.return_value = True

        with patch.object(channels, "get_system_proxy_manager", return_value=proxy_manager):
            channels._system_proxy_enabled = False
            try:
                assert channels._restore_managed_system_proxy() is True
            finally:
                channels._system_proxy_enabled = False

        proxy_manager.restore_proxy.assert_called_once()
        proxy_manager.discard_persisted_state.assert_not_called()
        proxy_manager.cleanup_stale_managed_proxy.assert_not_called()

    def test_restore_managed_system_proxy_discards_stale_marker_before_cleanup(self):
        from src.api import channels

        proxy_manager = MagicMock()
        proxy_manager.has_persisted_state.return_value = True
        proxy_manager.is_current_settings_managed.return_value = False

        with patch.object(channels, "get_system_proxy_manager", return_value=proxy_manager):
            channels._system_proxy_enabled = False
            try:
                assert channels._restore_managed_system_proxy() is True
            finally:
                channels._system_proxy_enabled = False

        proxy_manager.discard_persisted_state.assert_called_once()
        proxy_manager.restore_proxy.assert_not_called()
        proxy_manager.cleanup_stale_managed_proxy.assert_called_once()


class TestTransparentStartBlockers:
    @pytest.mark.asyncio
    async def test_start_sniffer_auto_fallback_to_proxy_only_when_tun_enabled(self):
        """透明模式被 TUN 阻止时，自动回退到显式代理模式。"""
        from src.api import channels

        request = channels.SnifferStartRequest(capture_mode="transparent")
        proxy_info = ProxyInfo(
            proxy_type=ProxyType.CLASH_VERGE,
            proxy_mode=ProxyMode.TUN,
            process_name="clash-verge.exe",
            is_tun_enabled=True,
        )

        sniffer = MagicMock()
        sniffer.port = 8888
        sniffer.start = AsyncMock(
            return_value=MagicMock(
                to_dict=MagicMock(
                    return_value={
                        "success": True,
                        "proxy_address": "127.0.0.1:8888",
                    }
                )
            )
        )
        proxy_manager = MagicMock()
        proxy_manager.set_proxy.return_value = True
        proxy_manager.has_active_proxy.return_value = False

        with patch.object(channels, "_detect_proxy_info", new=AsyncMock(return_value=proxy_info)), \
            patch.object(channels, "get_cert_installer", return_value=MagicMock(get_cert_info=MagicMock(return_value={"cert_installed": True}))), \
            patch.object(channels, "get_system_proxy_manager", return_value=proxy_manager), \
            patch.object(channels, "_restore_managed_system_proxy", return_value=True), \
            patch.object(channels, "get_sniffer", return_value=sniffer), \
            patch.object(channels, "_auto_prepare_wechat_channels_cache", return_value={}):
            result = await channels.start_sniffer(request)

        # 应成功启动（回退到 proxy_only），并带有警告信息
        assert result["success"] is True
        assert result["capture_mode"] == "proxy_only"
        assert "TUN" in result.get("error_message", "")

    @pytest.mark.asyncio
    async def test_start_sniffer_clears_stale_videos_after_success(self):
        from src.api import channels

        request = channels.SnifferStartRequest(capture_mode="proxy_only")
        proxy_info = ProxyInfo(
            proxy_type=ProxyType.CLASH_VERGE,
            proxy_mode=ProxyMode.SYSTEM_PROXY,
            process_name="verge-mihomo.exe",
            is_tun_enabled=False,
        )
        proxy_manager = MagicMock()
        proxy_manager.set_proxy.return_value = True

        sniffer = MagicMock()
        sniffer.port = 8899
        sniffer.start = AsyncMock(
            return_value=MagicMock(
                to_dict=MagicMock(
                    return_value={
                        "success": True,
                        "proxy_address": "127.0.0.1:8899",
                    }
                )
            )
        )

        with patch.object(channels, "_detect_proxy_info", new=AsyncMock(return_value=proxy_info)), \
            patch.object(channels, "get_cert_installer", return_value=MagicMock(get_cert_info=MagicMock(return_value={"cert_installed": True}))), \
            patch.object(channels, "get_system_proxy_manager", return_value=proxy_manager), \
            patch.object(channels, "_restore_managed_system_proxy", return_value=True), \
            patch.object(channels, "_pick_available_proxy_port", return_value=8899), \
            patch.object(channels, "get_sniffer", return_value=sniffer):
            previous_proxy_enabled = channels._system_proxy_enabled
            previous_active_port = channels._active_proxy_port
            channels._system_proxy_enabled = False
            try:
                result = await channels.start_sniffer(request)
            finally:
                channels._system_proxy_enabled = previous_proxy_enabled
                channels._active_proxy_port = previous_active_port

        assert result["success"] is True
        sniffer.clear_videos.assert_called_once()
        sniffer.proactively_recycle_wechat_renderer_on_startup.assert_called_once()
        assert "renderer_recovery" not in result

    @pytest.mark.asyncio
    async def test_shutdown_capture_resources_restores_proxy_and_stops_sniffer(self):
        from src.api import channels

        sniffer = MagicMock()
        sniffer.is_running = True
        sniffer.stop = AsyncMock(return_value=True)
        proxy_manager = MagicMock()
        proxy_manager.has_persisted_state.return_value = True

        with patch.object(channels, "get_sniffer", return_value=sniffer), \
            patch.object(channels, "get_system_proxy_manager", return_value=proxy_manager), \
            patch.object(channels, "_restore_managed_system_proxy", return_value=True) as restore_proxy:
            previous_proxy_enabled = channels._system_proxy_enabled
            previous_active_port = channels._active_proxy_port
            channels._system_proxy_enabled = True
            channels._active_proxy_port = 8899
            try:
                await channels.shutdown_capture_resources()
            finally:
                channels._system_proxy_enabled = previous_proxy_enabled
                channels._active_proxy_port = previous_active_port

        sniffer.stop.assert_awaited_once()
        restore_proxy.assert_called_once()


class TestCertificateWarning:
    def test_build_channels_certificate_warning_detects_missing_private_key(self):
        from src.api.channels import _build_channels_certificate_warning

        warning = _build_channels_certificate_warning(
            {
                "cert_installed": True,
                "cert_p12_exists": True,
                "wechat_p12_installed": False,
                "wechat_p12_subject_present": True,
            }
        )

        assert warning is not None
        assert "私钥" in warning
        assert "mitmproxy-ca.p12" in warning
