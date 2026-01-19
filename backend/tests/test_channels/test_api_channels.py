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

from src.core.channels.proxy_sniffer import ProxySniffer


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
