"""
数据模型属性测试

Property 9: Configuration Persistence Round-Trip
Property 11: Detected Videos Persistence Round-Trip
Property 13: Configuration Persistence Round-Trip (MultiModeCaptureConfig)
Validates: Requirements 6.5, 7.1-7.5, 10.1, 10.2
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
import json
import tempfile
import os

from src.core.channels.models import (
    SnifferState,
    EncryptionType,
    DetectedVideo,
    SnifferStatus,
    ChannelsConfig,
    ErrorCode,
    get_error_message,
    # New imports for deep research
    ProxyType,
    ProxyMode,
    CaptureMode,
    ProxyInfo,
    CaptureStatistics,
    RecoveryAttempt,
    DiagnosticInfo,
    WeChatProcess,
    MultiModeCaptureConfig,
    ExtendedErrorCode,
    get_extended_error_message,
)


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def channels_config_strategy(draw):
    """生成随机 ChannelsConfig"""
    return ChannelsConfig(
        proxy_port=draw(st.integers(min_value=1024, max_value=65535)),
        download_dir=draw(st.text(min_size=0, max_size=100).filter(lambda x: '\x00' not in x)),
        auto_decrypt=draw(st.booleans()),
        quality_preference=draw(st.sampled_from(["best", "1080p", "720p", "480p"])),
        clear_on_exit=draw(st.booleans()),
    )


@st.composite
def detected_video_strategy(draw):
    """生成随机 DetectedVideo"""
    return DetectedVideo(
        id=draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip() and '\x00' not in x)),
        url=draw(st.text(min_size=1, max_size=200).filter(lambda x: x.strip() and '\x00' not in x)),
        title=draw(st.one_of(st.none(), st.text(min_size=0, max_size=100).filter(lambda x: '\x00' not in x))),
        duration=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=36000))),
        resolution=draw(st.one_of(st.none(), st.sampled_from(["1080p", "720p", "480p", "360p"]))),
        filesize=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=10**10))),
        thumbnail=draw(st.one_of(st.none(), st.text(min_size=0, max_size=200).filter(lambda x: '\x00' not in x))),
        detected_at=draw(st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31)
        )),
        encryption_type=draw(st.sampled_from(list(EncryptionType))),
        decryption_key=draw(st.one_of(st.none(), st.text(min_size=0, max_size=64).filter(lambda x: '\x00' not in x))),
    )


@st.composite
def multi_mode_capture_config_strategy(draw):
    """生成随机 MultiModeCaptureConfig
    
    用于 Property 13: Configuration Persistence Round-Trip 测试
    """
    # 生成有效的 Clash API 地址
    host = draw(st.sampled_from(["127.0.0.1", "localhost", "192.168.1.1"]))
    port = draw(st.integers(min_value=1024, max_value=65535))
    clash_api_address = f"{host}:{port}"
    
    # 生成有效的恢复设置
    backoff_base = draw(st.floats(min_value=0.1, max_value=10.0))
    backoff_max = draw(st.floats(min_value=backoff_base, max_value=60.0))
    
    return MultiModeCaptureConfig(
        preferred_mode=draw(st.sampled_from([
            CaptureMode.HYBRID, CaptureMode.WINDIVERT, 
            CaptureMode.CLASH_API, CaptureMode.SYSTEM_PROXY
        ])),
        auto_fallback=draw(st.booleans()),
        clash_api_address=clash_api_address,
        clash_api_secret=draw(st.text(min_size=0, max_size=64).filter(lambda x: '\x00' not in x)),
        custom_proxy_address=draw(st.text(min_size=0, max_size=100).filter(lambda x: '\x00' not in x)),
        quic_blocking_enabled=draw(st.booleans()),
        target_processes=draw(st.lists(
            st.text(min_size=1, max_size=50).filter(lambda x: x.strip() and '\x00' not in x),
            min_size=1, max_size=10
        )),
        diagnostic_mode=draw(st.booleans()),
        log_all_traffic=draw(st.booleans()),
        windivert_filter=draw(st.text(min_size=0, max_size=200).filter(lambda x: '\x00' not in x)),
        ip_database_url=draw(st.text(min_size=0, max_size=200).filter(lambda x: '\x00' not in x)),
        no_detection_timeout=draw(st.integers(min_value=0, max_value=3600)),
        api_timeout=draw(st.integers(min_value=0, max_value=300)),
        max_recovery_attempts=draw(st.integers(min_value=0, max_value=10)),
        recovery_backoff_base=backoff_base,
        recovery_backoff_max=backoff_max,
    )


@st.composite
def proxy_info_strategy(draw):
    """生成随机 ProxyInfo"""
    return ProxyInfo(
        proxy_type=draw(st.sampled_from(list(ProxyType))),
        proxy_mode=draw(st.sampled_from(list(ProxyMode))),
        process_name=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50).filter(lambda x: '\x00' not in x))),
        process_pid=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=65535))),
        api_address=draw(st.one_of(st.none(), st.text(min_size=0, max_size=50).filter(lambda x: '\x00' not in x))),
        api_secret=draw(st.one_of(st.none(), st.text(min_size=0, max_size=64).filter(lambda x: '\x00' not in x))),
        is_tun_enabled=draw(st.booleans()),
        is_fake_ip_enabled=draw(st.booleans()),
    )


# ============================================================================
# Property 9: Configuration Persistence Round-Trip
# Validates: Requirements 7.1-7.5
# ============================================================================

class TestConfigurationPersistence:
    """
    Property 9: Configuration Persistence Round-Trip
    
    For any valid ChannelsConfig, saving the configuration and then loading it
    should produce an equivalent configuration object. All fields (proxy_port,
    download_dir, auto_decrypt, quality_preference) should be preserved.
    
    **Feature: weixin-channels-download, Property 9: Configuration Persistence Round-Trip**
    **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
    """

    @given(config=channels_config_strategy())
    @settings(max_examples=100)
    def test_config_dict_round_trip(self, config: ChannelsConfig):
        """配置对象 -> 字典 -> 配置对象 应该保持等价"""
        # Serialize to dict
        config_dict = config.to_dict()
        
        # Deserialize back
        restored = ChannelsConfig.from_dict(config_dict)
        
        # Verify all fields are preserved
        assert restored.proxy_port == config.proxy_port
        assert restored.download_dir == config.download_dir
        assert restored.auto_decrypt == config.auto_decrypt
        assert restored.quality_preference == config.quality_preference
        assert restored.clear_on_exit == config.clear_on_exit

    @given(config=channels_config_strategy())
    @settings(max_examples=100)
    def test_config_json_round_trip(self, config: ChannelsConfig):
        """配置对象 -> JSON -> 配置对象 应该保持等价"""
        # Serialize to JSON
        json_str = config.to_json()
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        
        # Deserialize back
        restored = ChannelsConfig.from_json(json_str)
        
        # Verify all fields are preserved
        assert restored.proxy_port == config.proxy_port
        assert restored.download_dir == config.download_dir
        assert restored.auto_decrypt == config.auto_decrypt
        assert restored.quality_preference == config.quality_preference
        assert restored.clear_on_exit == config.clear_on_exit

    def test_config_default_values(self):
        """测试默认配置值"""
        config = ChannelsConfig()
        assert config.proxy_port == 8888
        assert config.download_dir == ""
        assert config.auto_decrypt is True
        assert config.quality_preference == "best"
        assert config.clear_on_exit is False

    def test_config_from_partial_dict(self):
        """测试从部分字典创建配置（使用默认值）"""
        partial_dict = {"proxy_port": 9999}
        config = ChannelsConfig.from_dict(partial_dict)
        
        assert config.proxy_port == 9999
        assert config.download_dir == ""  # default
        assert config.auto_decrypt is True  # default


# ============================================================================
# Property 11: Detected Videos Persistence Round-Trip
# Validates: Requirements 6.5
# ============================================================================

class TestDetectedVideosPersistence:
    """
    Property 11: Detected Videos Persistence Round-Trip
    
    For any list of detected videos, persisting the list and then loading it
    should produce an equivalent list with all video metadata preserved
    (url, title, duration, detected_at, etc.).
    
    **Feature: weixin-channels-download, Property 11: Detected Videos Persistence Round-Trip**
    **Validates: Requirements 6.5**
    """

    @given(video=detected_video_strategy())
    @settings(max_examples=100)
    def test_video_dict_round_trip(self, video: DetectedVideo):
        """视频对象 -> 字典 -> 视频对象 应该保持等价"""
        # Serialize to dict
        video_dict = video.to_dict()
        
        # Deserialize back
        restored = DetectedVideo.from_dict(video_dict)
        
        # Verify all fields are preserved
        assert restored.id == video.id
        assert restored.url == video.url
        assert restored.title == video.title
        assert restored.duration == video.duration
        assert restored.resolution == video.resolution
        assert restored.filesize == video.filesize
        assert restored.thumbnail == video.thumbnail
        # datetime comparison with tolerance for microseconds
        assert abs((restored.detected_at - video.detected_at).total_seconds()) < 1
        assert restored.encryption_type == video.encryption_type
        assert restored.decryption_key == video.decryption_key

    @given(videos=st.lists(detected_video_strategy(), min_size=0, max_size=20))
    @settings(max_examples=100)
    def test_video_list_round_trip(self, videos: list):
        """视频列表 -> JSON -> 视频列表 应该保持等价"""
        # Serialize list to JSON
        video_dicts = [v.to_dict() for v in videos]
        json_str = json.dumps(video_dicts, ensure_ascii=False)
        
        # Deserialize back
        parsed = json.loads(json_str)
        restored_videos = [DetectedVideo.from_dict(d) for d in parsed]
        
        # Verify list length
        assert len(restored_videos) == len(videos)
        
        # Verify each video
        for original, restored in zip(videos, restored_videos):
            assert restored.id == original.id
            assert restored.url == original.url
            assert restored.title == original.title
            assert restored.duration == original.duration
            assert restored.encryption_type == original.encryption_type

    def test_video_to_dict_contains_all_fields(self):
        """测试 to_dict 包含所有必要字段"""
        video = DetectedVideo(
            id="test-123",
            url="https://example.com/video.mp4",
            title="Test Video",
            duration=120,
            resolution="1080p",
            filesize=1024000,
            thumbnail="https://example.com/thumb.jpg",
            detected_at=datetime(2024, 1, 1, 12, 0, 0),
            encryption_type=EncryptionType.XOR,
            decryption_key="abc123",
        )
        
        d = video.to_dict()
        
        assert "id" in d
        assert "url" in d
        assert "title" in d
        assert "duration" in d
        assert "resolution" in d
        assert "filesize" in d
        assert "thumbnail" in d
        assert "detected_at" in d
        assert "encryption_type" in d
        assert "decryption_key" in d


# ============================================================================
# Additional Unit Tests for Models
# ============================================================================

class TestSnifferStatus:
    """SnifferStatus 单元测试"""

    def test_status_to_dict(self):
        """测试状态转换为字典"""
        status = SnifferStatus(
            state=SnifferState.RUNNING,
            proxy_address="127.0.0.1:8888",
            proxy_port=8888,
            videos_detected=5,
            started_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        
        d = status.to_dict()
        
        assert d["state"] == "running"
        assert d["proxy_address"] == "127.0.0.1:8888"
        assert d["proxy_port"] == 8888
        assert d["videos_detected"] == 5
        assert d["started_at"] == "2024-01-01T12:00:00"

    def test_status_with_error(self):
        """测试带错误信息的状态"""
        status = SnifferStatus(
            state=SnifferState.ERROR,
            error_message="端口已被占用",
        )
        
        d = status.to_dict()
        
        assert d["state"] == "error"
        assert d["error_message"] == "端口已被占用"


class TestErrorMessages:
    """错误消息测试"""

    def test_get_error_message_with_params(self):
        """测试带参数的错误消息"""
        msg = get_error_message(ErrorCode.PORT_IN_USE, port=8888)
        assert "8888" in msg
        assert "占用" in msg

    def test_get_error_message_without_params(self):
        """测试不带参数的错误消息"""
        msg = get_error_message(ErrorCode.NETWORK_ERROR)
        assert "网络" in msg

    def test_get_error_message_unknown_code(self):
        """测试未知错误码"""
        msg = get_error_message("UNKNOWN_CODE")
        assert "未知错误" in msg


class TestEncryptionType:
    """EncryptionType 枚举测试"""

    def test_encryption_type_values(self):
        """测试加密类型值"""
        assert EncryptionType.NONE.value == "none"
        assert EncryptionType.XOR.value == "xor"
        assert EncryptionType.AES.value == "aes"
        assert EncryptionType.UNKNOWN.value == "unknown"

    def test_encryption_type_from_string(self):
        """测试从字符串创建枚举"""
        assert EncryptionType("xor") == EncryptionType.XOR
        assert EncryptionType("none") == EncryptionType.NONE


# ============================================================================
# Property 13: Configuration Persistence Round-Trip (MultiModeCaptureConfig)
# Validates: Requirements 10.1, 10.2
# ============================================================================

class TestMultiModeCaptureConfigPersistence:
    """
    Property 13: Configuration Persistence Round-Trip
    
    For any valid MultiModeCaptureConfig, saving it to disk and loading it back
    should produce an equivalent configuration object with all fields preserved.
    
    **Feature: weixin-channels-deep-research, Property 13: Configuration Persistence Round-Trip**
    **Validates: Requirements 10.1, 10.2**
    """

    @given(config=multi_mode_capture_config_strategy())
    @settings(max_examples=100)
    def test_config_dict_round_trip(self, config: MultiModeCaptureConfig):
        """配置对象 -> 字典 -> 配置对象 应该保持等价"""
        # Serialize to dict
        config_dict = config.to_dict()
        
        # Deserialize back
        restored = MultiModeCaptureConfig.from_dict(config_dict)
        
        # Verify all fields are preserved
        assert restored.preferred_mode == config.preferred_mode
        assert restored.auto_fallback == config.auto_fallback
        assert restored.clash_api_address == config.clash_api_address
        assert restored.clash_api_secret == config.clash_api_secret
        assert restored.custom_proxy_address == config.custom_proxy_address
        assert restored.quic_blocking_enabled == config.quic_blocking_enabled
        assert restored.target_processes == config.target_processes
        assert restored.diagnostic_mode == config.diagnostic_mode
        assert restored.log_all_traffic == config.log_all_traffic
        assert restored.windivert_filter == config.windivert_filter
        assert restored.ip_database_url == config.ip_database_url
        assert restored.no_detection_timeout == config.no_detection_timeout
        assert restored.api_timeout == config.api_timeout
        assert restored.max_recovery_attempts == config.max_recovery_attempts
        assert restored.recovery_backoff_base == config.recovery_backoff_base
        assert restored.recovery_backoff_max == config.recovery_backoff_max

    @given(config=multi_mode_capture_config_strategy())
    @settings(max_examples=100)
    def test_config_json_round_trip(self, config: MultiModeCaptureConfig):
        """配置对象 -> JSON -> 配置对象 应该保持等价"""
        # Serialize to JSON
        json_str = config.to_json()
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        
        # Deserialize back
        restored = MultiModeCaptureConfig.from_json(json_str)
        
        # Verify all fields are preserved
        assert restored.preferred_mode == config.preferred_mode
        assert restored.auto_fallback == config.auto_fallback
        assert restored.clash_api_address == config.clash_api_address
        assert restored.clash_api_secret == config.clash_api_secret
        assert restored.quic_blocking_enabled == config.quic_blocking_enabled
        assert restored.target_processes == config.target_processes
        assert restored.diagnostic_mode == config.diagnostic_mode
        assert restored.no_detection_timeout == config.no_detection_timeout
        assert restored.max_recovery_attempts == config.max_recovery_attempts

    @given(config=multi_mode_capture_config_strategy())
    @settings(max_examples=100)
    def test_config_file_round_trip(self, config: MultiModeCaptureConfig):
        """配置对象 -> 文件 -> 配置对象 应该保持等价"""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save to file
            config.save(temp_path)
            
            # Load from file
            restored = MultiModeCaptureConfig.load(temp_path)
            
            # Verify all fields are preserved
            assert restored.preferred_mode == config.preferred_mode
            assert restored.auto_fallback == config.auto_fallback
            assert restored.clash_api_address == config.clash_api_address
            assert restored.clash_api_secret == config.clash_api_secret
            assert restored.custom_proxy_address == config.custom_proxy_address
            assert restored.quic_blocking_enabled == config.quic_blocking_enabled
            assert restored.target_processes == config.target_processes
            assert restored.diagnostic_mode == config.diagnostic_mode
            assert restored.log_all_traffic == config.log_all_traffic
            assert restored.no_detection_timeout == config.no_detection_timeout
            assert restored.api_timeout == config.api_timeout
            assert restored.max_recovery_attempts == config.max_recovery_attempts
            assert restored.recovery_backoff_base == config.recovery_backoff_base
            assert restored.recovery_backoff_max == config.recovery_backoff_max
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_config_default_values(self):
        """测试默认配置值"""
        config = MultiModeCaptureConfig()
        assert config.preferred_mode == CaptureMode.HYBRID
        assert config.auto_fallback is True
        assert config.clash_api_address == "127.0.0.1:9090"
        assert config.clash_api_secret == ""
        assert config.quic_blocking_enabled is False
        assert config.diagnostic_mode is False
        assert config.no_detection_timeout == 60
        assert config.max_recovery_attempts == 3

    def test_config_from_partial_dict(self):
        """测试从部分字典创建配置（使用默认值）"""
        partial_dict = {"preferred_mode": "clash_api", "quic_blocking_enabled": True}
        config = MultiModeCaptureConfig.from_dict(partial_dict)
        
        assert config.preferred_mode == CaptureMode.CLASH_API
        assert config.quic_blocking_enabled is True
        assert config.auto_fallback is True  # default
        assert config.clash_api_address == "127.0.0.1:9090"  # default

    def test_config_load_nonexistent_file(self):
        """测试加载不存在的文件返回默认配置"""
        config = MultiModeCaptureConfig.load("/nonexistent/path/config.json")
        default = MultiModeCaptureConfig.get_defaults()
        
        assert config.preferred_mode == default.preferred_mode
        assert config.auto_fallback == default.auto_fallback


# ============================================================================
# Tests for ProxyInfo Persistence
# ============================================================================

class TestProxyInfoPersistence:
    """ProxyInfo 持久化测试"""

    @given(proxy_info=proxy_info_strategy())
    @settings(max_examples=100)
    def test_proxy_info_dict_round_trip(self, proxy_info: ProxyInfo):
        """ProxyInfo 对象 -> 字典 -> 对象 应该保持等价"""
        # Serialize to dict
        info_dict = proxy_info.to_dict()
        
        # Deserialize back
        restored = ProxyInfo.from_dict(info_dict)
        
        # Verify all fields are preserved
        assert restored.proxy_type == proxy_info.proxy_type
        assert restored.proxy_mode == proxy_info.proxy_mode
        assert restored.process_name == proxy_info.process_name
        assert restored.process_pid == proxy_info.process_pid
        assert restored.api_address == proxy_info.api_address
        assert restored.api_secret == proxy_info.api_secret
        assert restored.is_tun_enabled == proxy_info.is_tun_enabled
        assert restored.is_fake_ip_enabled == proxy_info.is_fake_ip_enabled

    @given(proxy_info=proxy_info_strategy())
    @settings(max_examples=100)
    def test_proxy_info_json_round_trip(self, proxy_info: ProxyInfo):
        """ProxyInfo 对象 -> JSON -> 对象 应该保持等价"""
        # Serialize to JSON
        json_str = proxy_info.to_json()
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        
        # Deserialize back
        restored = ProxyInfo.from_json(json_str)
        
        # Verify key fields are preserved
        assert restored.proxy_type == proxy_info.proxy_type
        assert restored.proxy_mode == proxy_info.proxy_mode
        assert restored.is_tun_enabled == proxy_info.is_tun_enabled
        assert restored.is_fake_ip_enabled == proxy_info.is_fake_ip_enabled


# ============================================================================
# Tests for New Enums
# ============================================================================

class TestNewEnums:
    """新增枚举类型测试"""

    def test_proxy_type_values(self):
        """测试 ProxyType 枚举值"""
        assert ProxyType.NONE.value == "none"
        assert ProxyType.CLASH.value == "clash"
        assert ProxyType.CLASH_VERGE.value == "clash_verge"
        assert ProxyType.CLASH_META.value == "clash_meta"
        assert ProxyType.SURGE.value == "surge"
        assert ProxyType.V2RAY.value == "v2ray"
        assert ProxyType.SHADOWSOCKS.value == "shadowsocks"
        assert ProxyType.OTHER.value == "other"

    def test_proxy_mode_values(self):
        """测试 ProxyMode 枚举值"""
        assert ProxyMode.NONE.value == "none"
        assert ProxyMode.SYSTEM_PROXY.value == "system_proxy"
        assert ProxyMode.TUN.value == "tun"
        assert ProxyMode.FAKE_IP.value == "fake_ip"
        assert ProxyMode.RULE.value == "rule"

    def test_capture_mode_new_values(self):
        """测试 CaptureMode 新增枚举值"""
        assert CaptureMode.WINDIVERT.value == "windivert"
        assert CaptureMode.CLASH_API.value == "clash_api"
        assert CaptureMode.SYSTEM_PROXY.value == "system_proxy"
        assert CaptureMode.HYBRID.value == "hybrid"

    def test_capture_mode_backward_compatibility(self):
        """测试 CaptureMode 向后兼容"""
        # 旧模式应该仍然存在
        assert CaptureMode.PROXY_ONLY.value == "proxy_only"
        assert CaptureMode.TRANSPARENT.value == "transparent"
        assert CaptureMode.PROXY.value == "proxy"


# ============================================================================
# Tests for Extended Error Messages
# ============================================================================

class TestExtendedErrorMessages:
    """扩展错误消息测试"""

    def test_extended_error_codes_exist(self):
        """测试扩展错误码存在"""
        assert hasattr(ExtendedErrorCode, 'PROXY_TUN_MODE')
        assert hasattr(ExtendedErrorCode, 'PROXY_FAKE_IP')
        assert hasattr(ExtendedErrorCode, 'CLASH_API_FAILED')
        assert hasattr(ExtendedErrorCode, 'WECHAT_NOT_RUNNING')
        assert hasattr(ExtendedErrorCode, 'RECOVERY_FAILED')
        assert hasattr(ExtendedErrorCode, 'CONFIG_INVALID')

    def test_get_extended_error_message(self):
        """测试获取扩展错误消息"""
        msg = get_extended_error_message(ExtendedErrorCode.PROXY_TUN_MODE)
        assert "TUN" in msg
        
        msg = get_extended_error_message(ExtendedErrorCode.WECHAT_NOT_RUNNING)
        assert "微信" in msg
        
        msg = get_extended_error_message(ExtendedErrorCode.RECOVERY_FAILED)
        assert "恢复" in msg

    def test_extended_error_message_unknown_code(self):
        """测试未知扩展错误码"""
        msg = get_extended_error_message("UNKNOWN_EXTENDED_CODE")
        assert "未知错误" in msg


# ============================================================================
# Tests for Configuration Validation
# ============================================================================

class TestConfigurationValidation:
    """配置验证测试"""

    def test_valid_config_passes_validation(self):
        """测试有效配置通过验证"""
        config = MultiModeCaptureConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_invalid_clash_api_address_format(self):
        """测试无效的 Clash API 地址格式"""
        config = MultiModeCaptureConfig(clash_api_address="invalid-address")
        errors = config.validate()
        assert any("格式" in e for e in errors)

    def test_invalid_clash_api_port(self):
        """测试无效的 Clash API 端口"""
        config = MultiModeCaptureConfig(clash_api_address="127.0.0.1:99999")
        errors = config.validate()
        assert any("端口" in e for e in errors)

    def test_negative_timeout(self):
        """测试负数超时值"""
        config = MultiModeCaptureConfig(no_detection_timeout=-1)
        errors = config.validate()
        assert any("超时" in e for e in errors)

    def test_empty_target_processes(self):
        """测试空的目标进程列表"""
        config = MultiModeCaptureConfig(target_processes=[])
        errors = config.validate()
        assert any("进程" in e for e in errors)

    def test_invalid_backoff_settings(self):
        """测试无效的退避设置"""
        config = MultiModeCaptureConfig(
            recovery_backoff_base=10.0,
            recovery_backoff_max=5.0  # max < base is invalid
        )
        errors = config.validate()
        assert any("退避" in e for e in errors)
