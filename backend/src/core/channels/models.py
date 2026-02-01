"""
微信视频号下载模块数据模型

定义嗅探器状态、视频信息、配置等数据结构。
包含代理检测、多模式捕获、错误恢复等功能的数据模型。
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from pathlib import Path
import json


class SnifferState(Enum):
    """嗅探器状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class EncryptionType(Enum):
    """加密类型"""
    NONE = "none"
    XOR = "xor"
    AES = "aes"
    UNKNOWN = "unknown"


class CaptureMode(Enum):
    """捕获模式"""
    # 旧模式（保持向后兼容）
    PROXY_ONLY = "proxy_only"      # 纯代理模式（mitmproxy，需要安装证书）
    TRANSPARENT = "transparent"     # 透明捕获模式（WinDivert 被动嗅探）
    PROXY = "proxy"                 # 代理模式（mitmproxy，推荐用于视频号）
    # 新模式（深度优化）
    WINDIVERT = "windivert"         # WinDivert透明捕获（无代理环境）
    CLASH_API = "clash_api"         # Clash API监控（Clash用户）
    SYSTEM_PROXY = "system_proxy"   # 系统代理拦截（其他代理用户）
    HYBRID = "hybrid"               # 混合模式（自动选择最佳策略）


class ProxyType(Enum):
    """代理软件类型"""
    NONE = "none"
    CLASH = "clash"
    CLASH_VERGE = "clash_verge"
    CLASH_META = "clash_meta"
    SURGE = "surge"
    V2RAY = "v2ray"
    SHADOWSOCKS = "shadowsocks"
    OTHER = "other"


class ProxyMode(Enum):
    """代理工作模式"""
    NONE = "none"
    SYSTEM_PROXY = "system_proxy"
    TUN = "tun"
    FAKE_IP = "fake_ip"
    RULE = "rule"


class DriverState(Enum):
    """驱动状态"""
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    LOADING = "loading"
    ERROR = "error"


class CaptureState(Enum):
    """捕获状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    RECOVERING = "recovering"  # 新增：恢复中状态


@dataclass
class VideoMetadata:
    """视频元数据"""
    title: Optional[str] = None
    duration: Optional[int] = None  # 秒
    resolution: Optional[str] = None
    filesize: Optional[int] = None  # 字节
    thumbnail: Optional[str] = None
    width: Optional[int] = None  # 视频宽度
    height: Optional[int] = None  # 视频高度


@dataclass
class ProxyInfo:
    """代理信息
    
    存储检测到的代理软件信息，包括类型、模式、API地址等。
    Validates: Requirements 1.2, 1.4, 1.5
    """
    proxy_type: ProxyType = ProxyType.NONE
    proxy_mode: ProxyMode = ProxyMode.NONE
    process_name: Optional[str] = None
    process_pid: Optional[int] = None
    api_address: Optional[str] = None  # e.g., "127.0.0.1:9090"
    api_secret: Optional[str] = None
    is_tun_enabled: bool = False
    is_fake_ip_enabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "proxy_type": self.proxy_type.value,
            "proxy_mode": self.proxy_mode.value,
            "process_name": self.process_name,
            "process_pid": self.process_pid,
            "api_address": self.api_address,
            "api_secret": self.api_secret,
            "is_tun_enabled": self.is_tun_enabled,
            "is_fake_ip_enabled": self.is_fake_ip_enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProxyInfo":
        """从字典创建实例"""
        proxy_type = data.get("proxy_type", "none")
        if isinstance(proxy_type, str):
            proxy_type = ProxyType(proxy_type)
        proxy_mode = data.get("proxy_mode", "none")
        if isinstance(proxy_mode, str):
            proxy_mode = ProxyMode(proxy_mode)
        return cls(
            proxy_type=proxy_type,
            proxy_mode=proxy_mode,
            process_name=data.get("process_name"),
            process_pid=data.get("process_pid"),
            api_address=data.get("api_address"),
            api_secret=data.get("api_secret"),
            is_tun_enabled=data.get("is_tun_enabled", False),
            is_fake_ip_enabled=data.get("is_fake_ip_enabled", False),
        )

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ProxyInfo":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class DetectedVideo:
    """检测到的视频"""
    id: str                          # 唯一标识
    url: str                         # 视频 URL
    title: Optional[str] = None      # 标题
    duration: Optional[int] = None   # 时长（秒）
    resolution: Optional[str] = None # 分辨率
    filesize: Optional[int] = None   # 文件大小（字节）
    thumbnail: Optional[str] = None  # 缩略图 URL
    detected_at: datetime = field(default_factory=datetime.now)
    encryption_type: EncryptionType = EncryptionType.UNKNOWN
    decryption_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 JSON 序列化"""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "duration": self.duration,
            "resolution": self.resolution,
            "filesize": self.filesize,
            "thumbnail": self.thumbnail,
            "detected_at": self.detected_at.isoformat(),
            "encryption_type": self.encryption_type.value,
            "decryption_key": self.decryption_key,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DetectedVideo":
        """从字典创建实例"""
        return cls(
            id=data["id"],
            url=data["url"],
            title=data.get("title"),
            duration=data.get("duration"),
            resolution=data.get("resolution"),
            filesize=data.get("filesize"),
            thumbnail=data.get("thumbnail"),
            detected_at=datetime.fromisoformat(data["detected_at"]) if data.get("detected_at") else datetime.now(),
            encryption_type=EncryptionType(data.get("encryption_type", "unknown")),
            decryption_key=data.get("decryption_key"),
        )


@dataclass
class SnifferStatus:
    """嗅探器状态"""
    state: SnifferState
    proxy_address: Optional[str] = None  # 代理地址 (e.g., "127.0.0.1:8888")
    proxy_port: int = 8888
    videos_detected: int = 0             # 检测到的视频数量
    started_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "state": self.state.value,
            "proxy_address": self.proxy_address,
            "proxy_port": self.proxy_port,
            "videos_detected": self.videos_detected,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "error_message": self.error_message,
        }


@dataclass
class SnifferStartResult:
    """启动结果"""
    success: bool
    proxy_address: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None  # PORT_IN_USE, PERMISSION_DENIED, etc.

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "proxy_address": self.proxy_address,
            "error_message": self.error_message,
            "error_code": self.error_code,
        }


@dataclass
class CertInfo:
    """证书信息"""
    exists: bool
    valid: bool
    expires_at: Optional[datetime] = None
    fingerprint: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "exists": self.exists,
            "valid": self.valid,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "fingerprint": self.fingerprint,
            "path": self.path,
        }


@dataclass
class CertGenerateResult:
    """证书生成结果"""
    success: bool
    cert_path: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "cert_path": self.cert_path,
            "error_message": self.error_message,
        }


@dataclass
class DecryptResult:
    """解密结果"""
    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    encryption_type: Optional[EncryptionType] = None
    key: Optional[bytes] = None
    additional_info: Optional[Dict[str, Any]] = None  # 额外信息（如缺少 moov box 的提示）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "output_path": self.output_path,
            "error_message": self.error_message,
            "encryption_type": self.encryption_type.value if self.encryption_type else None,
            "key": self.key.hex() if self.key else None,
            "additional_info": self.additional_info,
        }


@dataclass
class ChannelsConfig:
    """视频号下载配置"""
    proxy_port: int = 8888
    download_dir: str = ""           # 空字符串表示使用默认目录
    auto_decrypt: bool = True
    quality_preference: str = "best" # best, 1080p, 720p, etc.
    clear_on_exit: bool = False      # 退出时是否清空检测列表

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "proxy_port": self.proxy_port,
            "download_dir": self.download_dir,
            "auto_decrypt": self.auto_decrypt,
            "quality_preference": self.quality_preference,
            "clear_on_exit": self.clear_on_exit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelsConfig":
        """从字典创建实例"""
        return cls(
            proxy_port=data.get("proxy_port", 8888),
            download_dir=data.get("download_dir", ""),
            auto_decrypt=data.get("auto_decrypt", True),
            quality_preference=data.get("quality_preference", "best"),
            clear_on_exit=data.get("clear_on_exit", False),
        )

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ChannelsConfig":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))


# 错误码定义
class ErrorCode:
    """错误码常量"""
    # 代理相关
    PORT_IN_USE = "PORT_IN_USE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    # 证书相关
    CERT_MISSING = "CERT_MISSING"
    CERT_EXPIRED = "CERT_EXPIRED"
    CERT_INVALID = "CERT_INVALID"
    # 下载相关
    NETWORK_ERROR = "NETWORK_ERROR"
    VIDEO_EXPIRED = "VIDEO_EXPIRED"
    DOWNLOAD_CANCELLED = "DOWNLOAD_CANCELLED"
    # 解密相关
    DECRYPT_FAILED = "DECRYPT_FAILED"
    UNKNOWN_ENCRYPTION = "UNKNOWN_ENCRYPTION"
    # 透明捕获相关（新增）
    DRIVER_MISSING = "DRIVER_MISSING"
    DRIVER_LOAD_FAILED = "DRIVER_LOAD_FAILED"
    ADMIN_REQUIRED = "ADMIN_REQUIRED"
    PROCESS_NOT_FOUND = "PROCESS_NOT_FOUND"
    CAPTURE_FAILED = "CAPTURE_FAILED"


# 错误消息映射（中文）
ERROR_MESSAGES: Dict[str, str] = {
    ErrorCode.PORT_IN_USE: "端口 {port} 已被占用",
    ErrorCode.PERMISSION_DENIED: "没有权限启动代理服务",
    ErrorCode.CERT_MISSING: "CA 证书不存在",
    ErrorCode.CERT_EXPIRED: "CA 证书已过期",
    ErrorCode.CERT_INVALID: "CA 证书无效",
    ErrorCode.NETWORK_ERROR: "网络连接失败",
    ErrorCode.VIDEO_EXPIRED: "视频链接已过期",
    ErrorCode.DOWNLOAD_CANCELLED: "下载已取消",
    ErrorCode.DECRYPT_FAILED: "视频解密失败",
    ErrorCode.UNKNOWN_ENCRYPTION: "未知的加密格式",
    # 透明捕获相关（新增）
    ErrorCode.DRIVER_MISSING: "WinDivert 驱动未安装",
    ErrorCode.DRIVER_LOAD_FAILED: "WinDivert 驱动加载失败",
    ErrorCode.ADMIN_REQUIRED: "需要管理员权限",
    ErrorCode.PROCESS_NOT_FOUND: "目标进程未运行",
    ErrorCode.CAPTURE_FAILED: "流量捕获启动失败",
}


def get_error_message(error_code: str, **kwargs) -> str:
    """获取本地化错误消息
    
    Args:
        error_code: 错误码
        **kwargs: 消息模板参数
        
    Returns:
        本地化的错误消息
    """
    message = ERROR_MESSAGES.get(error_code, f"未知错误: {error_code}")
    try:
        return message.format(**kwargs)
    except KeyError:
        return message


# ========================================
# 透明捕获相关数据模型
# ========================================

@dataclass
class DriverStatus:
    """驱动状态详情"""
    state: DriverState
    version: Optional[str] = None
    path: Optional[str] = None
    error_message: Optional[str] = None
    is_admin: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "state": self.state.value,
            "version": self.version,
            "path": self.path,
            "error_message": self.error_message,
            "is_admin": self.is_admin,
        }


@dataclass
class DriverInstallResult:
    """驱动安装结果"""
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass
class CaptureStatistics:
    """捕获统计
    
    记录捕获过程中的各项统计数据。
    Validates: Requirements 7.1
    """
    packets_intercepted: int = 0
    connections_analyzed: int = 0  # 新增：分析的连接数
    connections_redirected: int = 0
    videos_detected: int = 0
    snis_extracted: int = 0  # 新增：提取的SNI数量
    ech_detected: int = 0  # 新增：检测到的ECH数量
    quic_blocked: int = 0  # 新增：阻止的QUIC包数量
    errors_recovered: int = 0  # 新增：恢复的错误数量
    last_detection_at: Optional[datetime] = None
    unrecognized_domains: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "packets_intercepted": self.packets_intercepted,
            "connections_analyzed": self.connections_analyzed,
            "connections_redirected": self.connections_redirected,
            "videos_detected": self.videos_detected,
            "snis_extracted": self.snis_extracted,
            "ech_detected": self.ech_detected,
            "quic_blocked": self.quic_blocked,
            "errors_recovered": self.errors_recovered,
            "last_detection_at": self.last_detection_at.isoformat() if self.last_detection_at else None,
            "unrecognized_domains": self.unrecognized_domains,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CaptureStatistics":
        """从字典创建实例"""
        last_detection = data.get("last_detection_at")
        if isinstance(last_detection, str):
            last_detection = datetime.fromisoformat(last_detection)
        return cls(
            packets_intercepted=data.get("packets_intercepted", 0),
            connections_analyzed=data.get("connections_analyzed", 0),
            connections_redirected=data.get("connections_redirected", 0),
            videos_detected=data.get("videos_detected", 0),
            snis_extracted=data.get("snis_extracted", 0),
            ech_detected=data.get("ech_detected", 0),
            quic_blocked=data.get("quic_blocked", 0),
            errors_recovered=data.get("errors_recovered", 0),
            last_detection_at=last_detection,
            unrecognized_domains=data.get("unrecognized_domains", []),
        )


@dataclass
class CaptureStatus:
    """捕获状态详情
    
    包含当前捕获的完整状态信息。
    Validates: Requirements 2.4, 7.1
    """
    state: CaptureState
    mode: CaptureMode
    statistics: CaptureStatistics = field(default_factory=CaptureStatistics)
    started_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    proxy_info: Optional["ProxyInfo"] = None  # 新增：代理信息
    available_modes: List[CaptureMode] = field(default_factory=list)  # 新增：可用模式

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "state": self.state.value,
            "mode": self.mode.value,
            "statistics": self.statistics.to_dict(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "proxy_info": self.proxy_info.to_dict() if self.proxy_info else None,
            "available_modes": [m.value for m in self.available_modes],
        }


@dataclass
class CaptureStartResult:
    """捕获启动结果"""
    success: bool
    mode: CaptureMode = CaptureMode.TRANSPARENT
    proxy_address: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "mode": self.mode.value,
            "proxy_address": self.proxy_address,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass
class HlsManifest:
    """HLS 清单"""
    url: str
    is_master: bool = False              # 是否为主清单
    duration: Optional[float] = None     # 总时长
    segment_count: int = 0               # 分片数量
    variants: List[str] = field(default_factory=list)  # 子清单 URL（主清单）
    detected_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "url": self.url,
            "is_master": self.is_master,
            "duration": self.duration,
            "segment_count": self.segment_count,
            "variants": self.variants,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class HlsSegment:
    """HLS 分片"""
    url: str
    sequence: int                        # 分片序号
    duration: float                      # 分片时长
    manifest_url: str                    # 所属清单 URL
    detected_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "url": self.url,
            "sequence": self.sequence,
            "duration": self.duration,
            "manifest_url": self.manifest_url,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class CaptureConfig:
    """透明捕获配置"""
    capture_mode: CaptureMode = CaptureMode.TRANSPARENT  # 默认使用 Windows 透明捕获模式
    use_windivert: bool = True
    target_processes: List[str] = field(default_factory=lambda: ["WeChat.exe", "WeChatAppEx.exe"])
    no_detection_timeout: int = 60  # 秒
    log_unrecognized_domains: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "capture_mode": self.capture_mode.value,
            "use_windivert": self.use_windivert,
            "target_processes": self.target_processes,
            "no_detection_timeout": self.no_detection_timeout,
            "log_unrecognized_domains": self.log_unrecognized_domains,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CaptureConfig":
        """从字典创建实例"""
        capture_mode = data.get("capture_mode", "transparent")  # 默认使用透明捕获模式
        if isinstance(capture_mode, str):
            capture_mode = CaptureMode(capture_mode)
        return cls(
            capture_mode=capture_mode,
            use_windivert=data.get("use_windivert", True),
            target_processes=data.get("target_processes", ["WeChat.exe", "WeChatAppEx.exe"]),
            no_detection_timeout=data.get("no_detection_timeout", 60),
            log_unrecognized_domains=data.get("log_unrecognized_domains", True),
        )

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "CaptureConfig":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))

    def save(self, path: str) -> None:
        """保存配置到文件"""
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "CaptureConfig":
        """从文件加载配置"""
        from pathlib import Path
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))


# ========================================
# 深度优化相关数据模型（新增）
# ========================================

@dataclass
class WeChatProcess:
    """微信进程信息
    
    存储微信相关进程的详细信息。
    Validates: Requirements 8.1, 8.2
    """
    pid: int
    name: str
    exe_path: str
    ports: Set[int] = field(default_factory=set)
    last_seen: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "pid": self.pid,
            "name": self.name,
            "exe_path": self.exe_path,
            "ports": list(self.ports),
            "last_seen": self.last_seen.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeChatProcess":
        """从字典创建实例"""
        last_seen = data.get("last_seen")
        if isinstance(last_seen, str):
            last_seen = datetime.fromisoformat(last_seen)
        return cls(
            pid=data["pid"],
            name=data["name"],
            exe_path=data["exe_path"],
            ports=set(data.get("ports", [])),
            last_seen=last_seen or datetime.now(),
        )


@dataclass
class RecoveryAttempt:
    """恢复尝试记录
    
    记录组件恢复尝试的详细信息。
    Validates: Requirements 9.1, 9.2, 9.4
    """
    component: str
    error: str
    attempt_number: int
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = False
    backoff_delay: float = 0.0  # 退避延迟（秒）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "component": self.component,
            "error": self.error,
            "attempt_number": self.attempt_number,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "backoff_delay": self.backoff_delay,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryAttempt":
        """从字典创建实例"""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return cls(
            component=data["component"],
            error=data["error"],
            attempt_number=data["attempt_number"],
            timestamp=timestamp or datetime.now(),
            success=data.get("success", False),
            backoff_delay=data.get("backoff_delay", 0.0),
        )


@dataclass
class DiagnosticInfo:
    """诊断信息
    
    包含用于调试和诊断的详细信息。
    Validates: Requirements 7.1, 7.2, 7.4
    """
    detected_snis: List[str] = field(default_factory=list)
    detected_ips: List[str] = field(default_factory=list)
    wechat_processes: List[WeChatProcess] = field(default_factory=list)
    proxy_info: Optional[ProxyInfo] = None
    recent_errors: List[str] = field(default_factory=list)
    capture_log: List[str] = field(default_factory=list)
    recovery_history: List[RecoveryAttempt] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "detected_snis": self.detected_snis,
            "detected_ips": self.detected_ips,
            "wechat_processes": [p.to_dict() for p in self.wechat_processes],
            "proxy_info": self.proxy_info.to_dict() if self.proxy_info else None,
            "recent_errors": self.recent_errors,
            "capture_log": self.capture_log,
            "recovery_history": [r.to_dict() for r in self.recovery_history],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiagnosticInfo":
        """从字典创建实例"""
        proxy_info_data = data.get("proxy_info")
        proxy_info = ProxyInfo.from_dict(proxy_info_data) if proxy_info_data else None
        return cls(
            detected_snis=data.get("detected_snis", []),
            detected_ips=data.get("detected_ips", []),
            wechat_processes=[WeChatProcess.from_dict(p) for p in data.get("wechat_processes", [])],
            proxy_info=proxy_info,
            recent_errors=data.get("recent_errors", []),
            capture_log=data.get("capture_log", []),
            recovery_history=[RecoveryAttempt.from_dict(r) for r in data.get("recovery_history", [])],
        )


@dataclass
class MultiModeCaptureConfig:
    """多模式捕获配置
    
    扩展的捕获配置，支持多种捕获模式和代理设置。
    Validates: Requirements 10.1, 10.2, 10.3, 10.4
    """
    # 模式设置
    preferred_mode: CaptureMode = CaptureMode.HYBRID
    auto_fallback: bool = True
    
    # 代理设置
    clash_api_address: str = "127.0.0.1:9090"
    clash_api_secret: str = ""
    custom_proxy_address: str = ""
    
    # QUIC设置
    quic_blocking_enabled: bool = False
    
    # 进程设置
    target_processes: List[str] = field(default_factory=lambda: [
        "WeChat.exe", "WeChatAppEx.exe", "WeChatApp.exe", 
        "WeChatBrowser.exe", "WeChatPlayer.exe", "Weixin.exe"
    ])
    
    # 诊断设置
    diagnostic_mode: bool = False
    log_all_traffic: bool = False
    
    # 高级设置
    windivert_filter: str = ""
    ip_database_url: str = ""
    
    # 超时设置
    no_detection_timeout: int = 60  # 秒
    api_timeout: int = 10  # API请求超时（秒）
    
    # 恢复设置
    max_recovery_attempts: int = 3
    recovery_backoff_base: float = 1.0  # 秒
    recovery_backoff_max: float = 30.0  # 秒

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "preferred_mode": self.preferred_mode.value,
            "auto_fallback": self.auto_fallback,
            "clash_api_address": self.clash_api_address,
            "clash_api_secret": self.clash_api_secret,
            "custom_proxy_address": self.custom_proxy_address,
            "quic_blocking_enabled": self.quic_blocking_enabled,
            "target_processes": self.target_processes,
            "diagnostic_mode": self.diagnostic_mode,
            "log_all_traffic": self.log_all_traffic,
            "windivert_filter": self.windivert_filter,
            "ip_database_url": self.ip_database_url,
            "no_detection_timeout": self.no_detection_timeout,
            "api_timeout": self.api_timeout,
            "max_recovery_attempts": self.max_recovery_attempts,
            "recovery_backoff_base": self.recovery_backoff_base,
            "recovery_backoff_max": self.recovery_backoff_max,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MultiModeCaptureConfig":
        """从字典创建实例"""
        preferred_mode = data.get("preferred_mode", "hybrid")
        if isinstance(preferred_mode, str):
            preferred_mode = CaptureMode(preferred_mode)
        return cls(
            preferred_mode=preferred_mode,
            auto_fallback=data.get("auto_fallback", True),
            clash_api_address=data.get("clash_api_address", "127.0.0.1:9090"),
            clash_api_secret=data.get("clash_api_secret", ""),
            custom_proxy_address=data.get("custom_proxy_address", ""),
            quic_blocking_enabled=data.get("quic_blocking_enabled", False),
            target_processes=data.get("target_processes", [
                "WeChat.exe", "WeChatAppEx.exe", "WeChatApp.exe",
                "WeChatBrowser.exe", "WeChatPlayer.exe", "Weixin.exe"
            ]),
            diagnostic_mode=data.get("diagnostic_mode", False),
            log_all_traffic=data.get("log_all_traffic", False),
            windivert_filter=data.get("windivert_filter", ""),
            ip_database_url=data.get("ip_database_url", ""),
            no_detection_timeout=data.get("no_detection_timeout", 60),
            api_timeout=data.get("api_timeout", 10),
            max_recovery_attempts=data.get("max_recovery_attempts", 3),
            recovery_backoff_base=data.get("recovery_backoff_base", 1.0),
            recovery_backoff_max=data.get("recovery_backoff_max", 30.0),
        )

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "MultiModeCaptureConfig":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))

    def validate(self) -> List[str]:
        """验证配置，返回错误列表
        
        Returns:
            错误消息列表，空列表表示配置有效
        """
        errors = []
        
        # 验证端口格式
        if self.clash_api_address:
            parts = self.clash_api_address.split(":")
            if len(parts) != 2:
                errors.append("Clash API地址格式无效，应为 host:port")
            else:
                try:
                    port = int(parts[1])
                    if not (1 <= port <= 65535):
                        errors.append("Clash API端口必须在1-65535范围内")
                except ValueError:
                    errors.append("Clash API端口必须是数字")
        
        # 验证超时设置
        if self.no_detection_timeout < 0:
            errors.append("检测超时不能为负数")
        if self.api_timeout < 0:
            errors.append("API超时不能为负数")
        
        # 验证恢复设置
        if self.max_recovery_attempts < 0:
            errors.append("最大恢复尝试次数不能为负数")
        if self.recovery_backoff_base < 0:
            errors.append("恢复退避基数不能为负数")
        if self.recovery_backoff_max < self.recovery_backoff_base:
            errors.append("恢复退避最大值不能小于基数")
        
        # 验证进程列表
        if not self.target_processes:
            errors.append("目标进程列表不能为空")
        
        return errors

    @classmethod
    def get_defaults(cls) -> "MultiModeCaptureConfig":
        """获取默认配置"""
        return cls()

    def save(self, path: str) -> None:
        """保存配置到文件"""
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "MultiModeCaptureConfig":
        """从文件加载配置"""
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))


# 更新错误码定义
class ExtendedErrorCode(ErrorCode):
    """扩展错误码常量
    
    包含深度优化功能的错误码。
    """
    # 代理相关（新增）
    PROXY_TUN_MODE = "PROXY_TUN_MODE"
    PROXY_FAKE_IP = "PROXY_FAKE_IP"
    CLASH_API_FAILED = "CLASH_API_FAILED"
    CLASH_AUTH_FAILED = "CLASH_AUTH_FAILED"
    # 捕获相关（新增）
    WECHAT_NOT_RUNNING = "WECHAT_NOT_RUNNING"
    ECH_DETECTED = "ECH_DETECTED"
    NO_VIDEO_DETECTED = "NO_VIDEO_DETECTED"
    # 恢复相关（新增）
    RECOVERY_FAILED = "RECOVERY_FAILED"
    # 配置相关（新增）
    CONFIG_INVALID = "CONFIG_INVALID"


# 扩展错误消息映射
EXTENDED_ERROR_MESSAGES: Dict[str, str] = {
    **ERROR_MESSAGES,
    # 代理相关
    ExtendedErrorCode.PROXY_TUN_MODE: "检测到代理软件使用TUN模式，请切换到系统代理模式",
    ExtendedErrorCode.PROXY_FAKE_IP: "检测到Fake-IP模式，将使用IP识别替代方案",
    ExtendedErrorCode.CLASH_API_FAILED: "无法连接到Clash API，请检查Clash是否运行",
    ExtendedErrorCode.CLASH_AUTH_FAILED: "Clash API认证失败，请检查API密钥",
    # 捕获相关
    ExtendedErrorCode.WECHAT_NOT_RUNNING: "未检测到微信进程，请先启动微信",
    ExtendedErrorCode.ECH_DETECTED: "检测到ECH加密，已切换到IP识别模式",
    ExtendedErrorCode.NO_VIDEO_DETECTED: "未检测到视频，请在微信中播放视频",
    # 恢复相关
    ExtendedErrorCode.RECOVERY_FAILED: "自动恢复失败，请手动重启捕获功能",
    # 配置相关
    ExtendedErrorCode.CONFIG_INVALID: "配置文件无效，已使用默认配置",
}


def get_extended_error_message(error_code: str, **kwargs) -> str:
    """获取扩展的本地化错误消息
    
    Args:
        error_code: 错误码
        **kwargs: 消息模板参数
        
    Returns:
        本地化的错误消息
    """
    message = EXTENDED_ERROR_MESSAGES.get(error_code, f"未知错误: {error_code}")
    try:
        return message.format(**kwargs)
    except KeyError:
        return message
