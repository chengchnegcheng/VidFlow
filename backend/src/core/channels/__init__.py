"""
微信视频号下载模块

提供代理嗅探、视频检测、下载和解密功能。
"""

from .models import (
    # 基础枚举
    SnifferState,
    EncryptionType,
    CaptureMode,
    DriverState,
    CaptureState,
    # 基础数据类
    DetectedVideo,
    SnifferStatus,
    SnifferStartResult,
    CertInfo,
    CertGenerateResult,
    DecryptResult,
    ChannelsConfig,
    VideoMetadata,
    # 透明捕获数据类
    DriverStatus,
    DriverInstallResult,
    CaptureStatistics,
    CaptureStatus,
    CaptureStartResult,
    HlsManifest,
    HlsSegment,
    CaptureConfig,
    # 错误处理
    ErrorCode,
    get_error_message,
)
from .platform_detector import PlatformDetector
from .certificate_manager import CertificateManager
from .video_decryptor import VideoDecryptor, decrypt_video, find_wechat_video_cache, list_cached_videos
from .proxy_sniffer import ProxySniffer
from .driver_manager import DriverManager
from .hls_assembler import HlsAssembler
from .traffic_capture import WinDivertCapture

__all__ = [
    # 基础枚举
    "SnifferState",
    "EncryptionType",
    "CaptureMode",
    "DriverState",
    "CaptureState",
    # 基础数据类
    "DetectedVideo",
    "SnifferStatus",
    "SnifferStartResult",
    "CertInfo",
    "CertGenerateResult",
    "DecryptResult",
    "ChannelsConfig",
    "VideoMetadata",
    # 透明捕获数据类
    "DriverStatus",
    "DriverInstallResult",
    "CaptureStatistics",
    "CaptureStatus",
    "CaptureStartResult",
    "HlsManifest",
    "HlsSegment",
    "CaptureConfig",
    # 错误处理
    "ErrorCode",
    "get_error_message",
    # 组件
    "PlatformDetector",
    "CertificateManager",
    "VideoDecryptor",
    "decrypt_video",
    "find_wechat_video_cache",
    "list_cached_videos",
    "ProxySniffer",
    "DriverManager",
    "HlsAssembler",
    "WinDivertCapture",
]
