"""
WinDivert 透明流量捕获服务

使用 WinDivert 驱动透明拦截 TCP 流量并 NAT 转发到本地代理。
集成 ECHHandler、WeChatProcessManager、VideoURLExtractor 进行深度优化。

Validates: Requirements 3.2, 6.2, 6.3, 8.2
"""

import sys
import socket
import struct
import logging
import asyncio
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock, Event
from typing import Optional, List, Dict, Set, Callable, Any
from concurrent.futures import ThreadPoolExecutor

from .models import (
    CaptureMode,
    CaptureState,
    CaptureStatistics,
    CaptureStatus,
    CaptureStartResult,
    CaptureConfig,
    ErrorCode,
    get_error_message,
)
from .driver_manager import DriverManager
from .ech_handler import ECHHandler
from .video_url_extractor import VideoURLExtractor, ExtractedVideo
from .wechat_process_manager import WeChatProcessManager


logger = logging.getLogger(__name__)


# 默认视频号相关域名（用于 DNS 解析获取 IP）
DEFAULT_VIDEO_DOMAINS = [
    # 主要视频域名
    "finder.video.qq.com",
    "findermp.video.qq.com",
    "findervideodownload.video.qq.com",
    # 微信渠道域名
    "channels.weixin.qq.com",
    "szextshort.weixin.qq.com",
    "szshort.weixin.qq.com",
    "szvideo.weixin.qq.com",
    # 图片/缩略图域名
    "mpvideo.qpic.cn",
    "ugc.qpic.cn",
    "puui.qpic.cn",
    # 国际版域名
    "finder.video.wechat.com",
    # 动态/短视频域名
    "wxsnsdy.video.qq.com",
    "wxsnsdythumb.video.qq.com",
    "wxsnsdy.tc.qq.com",
    "wxsnsdythumb.tc.qq.com",
    # 直播相关
    "finder.live.qq.com",
    "finderlivevideo.video.qq.com",
    # 其他
    "vweixinf.tc.qq.com",
    "finderim.qq.com",
    # 小程序视频（关键！这是实际视频下载的域名）
    "wxapp.tc.qq.com",
    "stodownload.wxapp.tc.qq.com",
    # 腾讯视频 CDN
    "vd.video.qq.com",
    "vd2.video.qq.com",
    "vd3.video.qq.com",
    "apd-vlive.apdcdn.tc.qq.com",
    "apd-ugcvideo.apdcdn.tc.qq.com",
]

# 进程端口缓存过期时间（秒）
PROCESS_CACHE_TTL = 5.0
# 进程端口缓存刷新间隔（秒）
PROCESS_CACHE_REFRESH_INTERVAL = 2.0


class WinDivertCapture:
    """WinDivert 透明流量捕获服务
    
    使用 WinDivert 驱动透明拦截目标进程的 TCP 连接。
    支持两种模式：
    1. NAT 模式：将流量重定向到本地代理（需要 mitmproxy）
    2. 被动嗅探模式：只提取 SNI，不修改流量（不需要 mitmproxy）
    
    集成组件：
    - ECHHandler: 处理ECH加密场景，提供IP-based识别
    - WeChatProcessManager: 优化进程过滤，使用缓存提高性能
    - VideoURLExtractor: 统一URL处理，支持去重和过期检测
    
    Validates: Requirements 3.2, 6.2, 6.3, 8.2
    """
    
    # NAT 重定向模式：将流量重定向到本地代理
    # 设置为 False 以启用 NAT 重定向，True 则只做被动嗅探
    PASSIVE_MODE = False
    
    def __init__(
        self,
        proxy_port: int = 8888,
        target_domains: Optional[List[str]] = None,
        target_processes: Optional[List[str]] = None,
        driver_dir: Optional[Path] = None,
    ):
        """初始化透明捕获服务
        
        Args:
            proxy_port: 本地代理端口
            target_domains: 目标域名列表
            target_processes: 目标进程列表
            driver_dir: WinDivert 驱动目录
        """
        self.proxy_port = proxy_port
        self.target_domains = target_domains or DEFAULT_VIDEO_DOMAINS
        # 添加更多微信相关进程名
        self.target_processes = target_processes or [
            "WeChat.exe",
            "WeChatAppEx.exe",
            "WeChatApp.exe",
            "WeChatBrowser.exe",
            "WeChatPlayer.exe",
            "WeChatUpdate.exe",
            "WeChatOCR.exe",
            "WeChatUtility.exe",
            "WeChatWeb.exe",
            "Weixin.exe",  # 微信主进程
            "WXWork.exe",  # 企业微信
            "WXWorkWeb.exe",
        ]
        
        self._driver_manager = DriverManager(driver_dir)
        self._state = CaptureState.STOPPED
        self._statistics = CaptureStatistics()
        self._started_at: Optional[datetime] = None
        self._error_message: Optional[str] = None
        self._error_code: Optional[str] = None
        
        self._capture_thread: Optional[Thread] = None
        self._process_cache_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._lock = Lock()
        
        # 目标 IP 地址集合（从域名解析）
        self._target_ips: Set[str] = set()
        
        # 已知的腾讯 IP 前缀（用于宽松匹配）
        self._known_ip_prefixes: List[str] = []
        
        # 连接跟踪表：(src_ip, src_port, dst_ip, dst_port) -> original_dst
        self._connection_table: Dict[tuple, tuple] = {}
        self._connection_last_seen: Dict[tuple, datetime] = {}
        
        # WinDivert 句柄
        self._handle = None
        
        # 视频检测回调
        self._on_packet_intercepted: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # 进程端口缓存：port -> (process_name, timestamp)
        # 用于快速查找端口对应的进程，避免每个包都调用 psutil
        self._process_port_cache: Dict[int, tuple] = {}
        self._process_cache_lock = Lock()
        self._target_process_ports: Set[int] = set()  # 目标进程的端口集合
        
        # QUIC 阻止句柄（用于阻止 UDP 443 流量，强制回退到 TCP）
        self._quic_block_handle = None
        self._quic_block_thread: Optional[Thread] = None
        
        # 被动嗅探模式：已检测到的 SNI 和对应的视频 URL
        self._detected_snis: Dict[str, datetime] = {}  # SNI -> 检测时间
        self._sni_lock = Lock()
        
        # SNI 检测回调
        self._on_sni_detected: Optional[Callable[[str, str, int], None]] = None  # (sni, dst_ip, dst_port)
        
        # 代理软件监控（用于 Fake-IP/ECH 场景）
        self._proxy_monitor_thread: Optional[Thread] = None
        self._proxy_processes = [
            "clash", "clash-verge", "verge-mihomo", "mihomo",
            "clash-core", "clash-meta", "v2ray", "xray", "sing-box",
        ]
        
        # 集成新组件（深度优化）
        self._ech_handler = ECHHandler()
        self._video_url_extractor = VideoURLExtractor()
        self._wechat_process_manager = WeChatProcessManager(refresh_interval=PROCESS_CACHE_REFRESH_INTERVAL)
        
        # 视频检测回调（用于ExtractedVideo）
        self._on_video_extracted: Optional[Callable[[ExtractedVideo], None]] = None

    @property
    def is_running(self) -> bool:
        """捕获是否正在运行"""
        return self._state == CaptureState.RUNNING
    
    def set_on_sni_detected(self, callback: Callable[[str, str, int], None]) -> None:
        """设置 SNI 检测回调
        
        Args:
            callback: 检测到 SNI 时的回调函数，参数为 (sni, dst_ip, dst_port)
        """
        self._on_sni_detected = callback
    
    def set_on_video_extracted(self, callback: Callable[[ExtractedVideo], None]) -> None:
        """设置视频提取回调
        
        Args:
            callback: 提取到视频时的回调函数，参数为 ExtractedVideo
        """
        self._on_video_extracted = callback
    
    def set_on_packet_intercepted(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """设置数据包拦截回调
        
        Args:
            callback: 拦截到数据包时的回调函数
        """
        self._on_packet_intercepted = callback
    
    @staticmethod
    def extract_sni_from_tls(payload: bytes) -> Optional[str]:
        """从 TLS ClientHello 中提取 SNI
        
        Args:
            payload: TCP 负载数据
            
        Returns:
            SNI 域名，如果无法提取则返回 None
        """
        try:
            if len(payload) < 5:
                return None
            
            # TLS Record Header
            content_type = payload[0]
            if content_type != 0x16:  # Handshake
                return None
            
            # TLS Version (2 bytes) + Length (2 bytes)
            record_length = struct.unpack(">H", payload[3:5])[0]
            if len(payload) < 5 + record_length:
                return None
            
            # Handshake Header
            handshake_type = payload[5]
            if handshake_type != 0x01:  # ClientHello
                return None
            
            # Skip: Handshake Length (3 bytes) + Client Version (2 bytes) + Random (32 bytes)
            offset = 5 + 1 + 3 + 2 + 32
            
            if len(payload) < offset + 1:
                return None
            
            # Session ID Length
            session_id_length = payload[offset]
            offset += 1 + session_id_length
            
            if len(payload) < offset + 2:
                return None
            
            # Cipher Suites Length
            cipher_suites_length = struct.unpack(">H", payload[offset:offset+2])[0]
            offset += 2 + cipher_suites_length
            
            if len(payload) < offset + 1:
                return None
            
            # Compression Methods Length
            compression_methods_length = payload[offset]
            offset += 1 + compression_methods_length
            
            if len(payload) < offset + 2:
                return None
            
            # Extensions Length
            extensions_length = struct.unpack(">H", payload[offset:offset+2])[0]
            offset += 2
            
            extensions_end = offset + extensions_length
            
            # Parse Extensions
            while offset + 4 <= extensions_end and offset + 4 <= len(payload):
                ext_type = struct.unpack(">H", payload[offset:offset+2])[0]
                ext_length = struct.unpack(">H", payload[offset+2:offset+4])[0]
                offset += 4
                
                if ext_type == 0x0000:  # SNI Extension
                    if offset + 2 > len(payload):
                        return None
                    
                    # SNI List Length
                    sni_list_length = struct.unpack(">H", payload[offset:offset+2])[0]
                    offset += 2
                    
                    if offset + 3 > len(payload):
                        return None
                    
                    # SNI Type (1 byte) + SNI Length (2 bytes)
                    sni_type = payload[offset]
                    sni_length = struct.unpack(">H", payload[offset+1:offset+3])[0]
                    offset += 3
                    
                    if sni_type == 0x00 and offset + sni_length <= len(payload):  # Host Name
                        sni = payload[offset:offset+sni_length].decode('ascii', errors='ignore')
                        return sni
                    
                    return None
                
                offset += ext_length
            
            return None
            
        except Exception:
            return None
    
    async def start(self) -> CaptureStartResult:
        """启动透明捕获
        
        Returns:
            CaptureStartResult: 启动结果
        """
        if self._state == CaptureState.RUNNING:
            return CaptureStartResult(
                success=True,
                mode=CaptureMode.TRANSPARENT,
                proxy_address=f"127.0.0.1:{self.proxy_port}",
            )
        
        if self._state in (CaptureState.STARTING, CaptureState.STOPPING):
            # 检查是否卡在过渡状态超过 10 秒，如果是则强制重置
            if self._started_at:
                elapsed = (datetime.now() - self._started_at).total_seconds()
                if elapsed > 10:
                    logger.warning(f"Capture stuck in {self._state.value} state for {elapsed:.1f}s, forcing reset")
                    await self.stop()
                    self._state = CaptureState.STOPPED
                else:
                    return CaptureStartResult(
                        success=False,
                        mode=CaptureMode.TRANSPARENT,
                        error_message="捕获正在启动或停止中",
                    )
            else:
                # 没有启动时间记录，强制重置状态
                logger.warning(f"Capture in {self._state.value} state without timestamp, forcing reset")
                self._state = CaptureState.STOPPED
        
        # 检查平台
        if sys.platform != 'win32':
            return CaptureStartResult(
                success=False,
                mode=CaptureMode.TRANSPARENT,
                error_code=ErrorCode.CAPTURE_FAILED,
                error_message="透明捕获仅支持 Windows 平台",
            )
        
        # 检查管理员权限
        if not self._driver_manager.check_admin_privileges():
            self._state = CaptureState.ERROR
            self._error_code = ErrorCode.ADMIN_REQUIRED
            self._error_message = get_error_message(ErrorCode.ADMIN_REQUIRED)
            return CaptureStartResult(
                success=False,
                mode=CaptureMode.TRANSPARENT,
                error_code=self._error_code,
                error_message=self._error_message,
            )
        
        # 检查驱动
        if not self._driver_manager.is_installed():
            self._state = CaptureState.ERROR
            self._error_code = ErrorCode.DRIVER_MISSING
            self._error_message = get_error_message(ErrorCode.DRIVER_MISSING)
            return CaptureStartResult(
                success=False,
                mode=CaptureMode.TRANSPARENT,
                error_code=self._error_code,
                error_message=self._error_message,
            )
        
        self._state = CaptureState.STARTING
        self._error_message = None
        self._error_code = None
        
        try:
            # 解析目标域名获取 IP
            await self._resolve_target_ips()
            
            if not self._target_ips:
                logger.warning("No target IPs resolved, capture may not work")
            
            # 启动微信进程管理器（替代旧的进程缓存线程）
            self._wechat_process_manager.start_monitoring()
            logger.info("WeChat process manager started")
            
            # 等待缓存初始化
            await asyncio.sleep(0.5)
            
            # 启用 QUIC 阻止功能（强制回退到 TCP）
            self._quic_block_thread = Thread(target=self._quic_block_loop, daemon=True)
            self._quic_block_thread.start()
            logger.info("QUIC blocking enabled (UDP 443 will be dropped to force TCP fallback)")
            
            # 启动代理监控线程（用于 ECH/Fake-IP 场景）
            self._proxy_monitor_thread = Thread(target=self._proxy_monitor_loop, daemon=True)
            self._proxy_monitor_thread.start()
            logger.info("Proxy monitor enabled for ECH/Fake-IP scenarios")
            
            # 启动捕获线程
            self._stop_event.clear()
            self._capture_thread = Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            
            # 等待启动
            for _ in range(50):  # 最多等待 5 秒
                await asyncio.sleep(0.1)
                if self._state == CaptureState.RUNNING:
                    break
                if self._state == CaptureState.ERROR:
                    return CaptureStartResult(
                        success=False,
                        mode=CaptureMode.TRANSPARENT,
                        error_code=self._error_code,
                        error_message=self._error_message or "捕获启动失败",
                    )
            
            if self._state != CaptureState.RUNNING:
                self._state = CaptureState.ERROR
                self._error_message = "捕获启动超时"
                return CaptureStartResult(
                    success=False,
                    mode=CaptureMode.TRANSPARENT,
                    error_message=self._error_message,
                )
            
            self._started_at = datetime.now()
            logger.info(f"Transparent capture started, target IPs: {len(self._target_ips)}")
            
            return CaptureStartResult(
                success=True,
                mode=CaptureMode.TRANSPARENT,
                proxy_address=f"127.0.0.1:{self.proxy_port}",
            )
            
        except Exception as e:
            self._state = CaptureState.ERROR
            self._error_message = str(e)
            self._error_code = ErrorCode.CAPTURE_FAILED
            logger.exception("Failed to start transparent capture")
            return CaptureStartResult(
                success=False,
                mode=CaptureMode.TRANSPARENT,
                error_code=self._error_code,
                error_message=self._error_message,
            )

    async def stop(self) -> bool:
        """停止透明捕获
        
        Returns:
            停止成功返回 True
        """
        if self._state == CaptureState.STOPPED:
            return True
        
        if self._state == CaptureState.STOPPING:
            return False
        
        self._state = CaptureState.STOPPING
        
        try:
            # 发送停止信号
            self._stop_event.set()
            
            # 等待捕获线程结束
            if self._capture_thread and self._capture_thread.is_alive():
                self._capture_thread.join(timeout=5)
            
            # 等待 QUIC 阻止线程结束
            if self._quic_block_thread and self._quic_block_thread.is_alive():
                self._quic_block_thread.join(timeout=2)
            
            # 等待代理监控线程结束
            if self._proxy_monitor_thread and self._proxy_monitor_thread.is_alive():
                self._proxy_monitor_thread.join(timeout=2)
            
            # 停止微信进程管理器
            self._wechat_process_manager.stop_monitoring()
            
            # 清理资源
            self._cleanup()
            
            self._capture_thread = None
            self._quic_block_thread = None
            self._proxy_monitor_thread = None
            self._state = CaptureState.STOPPED
            self._started_at = None
            
            # 清除视频提取器的ID缓存
            self._video_url_extractor.clear_extracted_ids()
            
            logger.info("Transparent capture stopped")
            return True
            
        except Exception as e:
            logger.exception("Failed to stop transparent capture")
            self._state = CaptureState.ERROR
            self._error_message = str(e)
            return False
    
    def _cleanup(self) -> None:
        """清理资源"""
        with self._lock:
            # 关闭 WinDivert 句柄（如果还没有被关闭）
            if self._handle:
                try:
                    # 检查 handle 是否已经关闭
                    if hasattr(self._handle, 'is_opened') and self._handle.is_opened():
                        self._handle.close()
                    elif hasattr(self._handle, 'handle') and self._handle.handle:
                        # 如果没有 is_opened 方法，检查内部 handle
                        self._handle.close()
                except (RuntimeError, Exception) as e:
                    # 忽略 "handle is not open" 错误
                    logger.debug(f"Error closing WinDivert handle (may already be closed): {e}")
                finally:
                    self._handle = None
            
            # 关闭 QUIC 阻止句柄
            if self._quic_block_handle:
                try:
                    if hasattr(self._quic_block_handle, 'is_opened') and self._quic_block_handle.is_opened():
                        self._quic_block_handle.close()
                    elif hasattr(self._quic_block_handle, 'handle') and self._quic_block_handle.handle:
                        self._quic_block_handle.close()
                except (RuntimeError, Exception) as e:
                    logger.debug(f"Error closing QUIC block handle: {e}")
                finally:
                    self._quic_block_handle = None

            # 清空连接跟踪表
            self._connection_table.clear()
            self._connection_last_seen.clear()

        # 清空进程端口缓存
        with self._process_cache_lock:
            self._process_port_cache.clear()
            self._target_process_ports.clear()
    
    def get_status(self) -> CaptureStatus:
        """获取捕获状态
        
        Returns:
            CaptureStatus: 当前状态
        """
        return CaptureStatus(
            state=self._state,
            mode=CaptureMode.TRANSPARENT,
            statistics=self._statistics,
            started_at=self._started_at,
            error_message=self._error_message,
            error_code=self._error_code,
        )
    
    def set_target_processes(self, processes: List[str]) -> None:
        """更新目标进程列表（热更新）
        
        Args:
            processes: 新的目标进程列表
        """
        with self._lock:
            # 只在进程列表真正改变时才记录日志
            if self.target_processes != processes:
                self.target_processes = processes
                logger.info(f"Target processes updated: {processes}")
            else:
                self.target_processes = processes
    
    def set_target_domains(self, domains: List[str]) -> None:
        """更新目标域名列表
        
        Args:
            domains: 新的目标域名列表
        """
        with self._lock:
            self.target_domains = domains
            # 异步重新解析 IP
            asyncio.create_task(self._resolve_target_ips())
    
    async def _resolve_target_ips(self) -> None:
        """解析目标域名获取 IP 地址（并行解析，带超时）"""
        new_ips = set()
        fake_ip_count = 0
        
        # 已知的虚假 IP 前缀（代理软件常用）
        fake_ip_prefixes = [
            "198.18.",  # Clash/Surge 等代理软件的虚假 IP
            "198.19.",
            "100.64.",  # CGNAT
        ]
        
        # DNS 解析超时（秒）
        DNS_TIMEOUT = 2.0
        
        async def resolve_single_domain(domain: str) -> List[tuple]:
            """解析单个域名，带超时"""
            try:
                infos = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, socket.getaddrinfo, domain, 443, socket.AF_INET
                    ),
                    timeout=DNS_TIMEOUT
                )
                return [(domain, info[4][0]) for info in infos]
            except asyncio.TimeoutError:
                logger.warning(f"DNS timeout for {domain}")
                return []
            except socket.gaierror as e:
                logger.warning(f"Failed to resolve {domain}: {e}")
                return []
            except Exception as e:
                logger.warning(f"Error resolving {domain}: {e}")
                return []
        
        # 并行解析所有域名
        tasks = [resolve_single_domain(domain) for domain in self.target_domains]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                continue
            for domain, ip in result:
                # 检查是否是代理软件的虚假 IP
                is_fake = any(ip.startswith(prefix) for prefix in fake_ip_prefixes)
                if is_fake:
                    fake_ip_count += 1
                    logger.warning(f"Detected fake IP for {domain}: {ip} (proxy software may be active)")
                
                new_ips.add(ip)
                logger.debug(f"Resolved {domain} -> {ip}{' (fake)' if is_fake else ''}")
        
        # 添加一些已知的腾讯视频 CDN IP 段（作为备用）
        # 这些是腾讯云/腾讯视频常用的 IP 段
        known_tencent_ip_prefixes = [
            "183.3.", "183.47.", "183.60.", "183.61.",
            "14.17.", "14.18.", "14.29.",
            "113.96.", "113.105.", "113.108.",
            "119.147.", "119.167.",
            "125.39.",
            "180.163.",
            "203.205.",
            "111.161.", "111.206.",
            "101.226.", "101.227.",
            "58.250.", "58.251.",
            "59.36.", "59.37.",
            "61.151.",
            "121.51.",
            "140.207.",
            "182.254.",
            "211.152.",
            "223.167.",
        ]
        
        with self._lock:
            self._target_ips = new_ips
            # 保存已知的 IP 前缀用于宽松匹配
            self._known_ip_prefixes = known_tencent_ip_prefixes
            # 如果检测到代理软件，添加 Fake-IP 网段到前缀列表
            if fake_ip_count > 0:
                self._known_ip_prefixes.extend(["198.18.", "198.19."])
                logger.info("Added Fake-IP prefixes (198.18.x, 198.19.x) to target list for proxy compatibility")
        
        if fake_ip_count > 0:
            logger.warning(f"Detected {fake_ip_count} fake IPs - proxy software (Clash/Surge/etc.) may be active")
            logger.warning("Consider disabling proxy software for better video capture")
        
        logger.info(f"Resolved {len(new_ips)} target IPs from {len(self.target_domains)} domains")

    def _build_filter_string(self) -> str:
        """构建 WinDivert 过滤规则字符串
        
        Returns:
            WinDivert 过滤规则
        """
        # 只捕获微信相关 IP 的流量，避免影响其他网络访问
        # 这样可以确保不会影响正常上网
        if self._target_ips:
            # 构建 IP 过滤列表（最多取前 20 个 IP，避免过滤规则太长）
            ip_list = list(self._target_ips)[:20]
            ip_conditions = " or ".join([f"ip.DstAddr == {ip}" for ip in ip_list])
            filter_str = f"outbound and tcp and (tcp.DstPort == 80 or tcp.DstPort == 443) and ({ip_conditions})"
            logger.info(f"Using targeted filter for {len(ip_list)} WeChat IPs")
            return filter_str
        else:
            # 如果没有解析到 IP，使用宽松规则但会在代码中快速过滤
            logger.warning("No target IPs resolved, using broad filter (will filter in code)")
            return "outbound and tcp and (tcp.DstPort == 80 or tcp.DstPort == 443) and ip.DstAddr != 127.0.0.1"
    
    @staticmethod
    def extract_http_url(payload: bytes) -> Optional[str]:
        """从 HTTP 请求中提取 URL
        
        Args:
            payload: TCP 负载数据
            
        Returns:
            完整的 HTTP URL，如果无法提取则返回 None
        """
        try:
            if len(payload) < 16:
                return None
            
            # 检查是否是 HTTP 请求
            # HTTP 请求以 GET, POST, HEAD 等方法开头
            http_methods = [b'GET ', b'POST ', b'HEAD ', b'PUT ', b'DELETE ']
            
            is_http = False
            for method in http_methods:
                if payload.startswith(method):
                    is_http = True
                    break
            
            if not is_http:
                return None
            
            # 解析 HTTP 请求
            try:
                # 找到第一行结束
                first_line_end = payload.find(b'\r\n')
                if first_line_end == -1:
                    first_line_end = payload.find(b'\n')
                if first_line_end == -1:
                    return None
                
                first_line = payload[:first_line_end].decode('ascii', errors='ignore')
                
                # 解析请求行: METHOD PATH HTTP/1.x
                parts = first_line.split(' ')
                if len(parts) < 2:
                    return None
                
                path = parts[1]
                
                # 提取 Host 头
                host = None
                headers_start = first_line_end + 2
                headers_section = payload[headers_start:].decode('ascii', errors='ignore')
                
                for line in headers_section.split('\r\n'):
                    if line.lower().startswith('host:'):
                        host = line[5:].strip()
                        break
                    if line == '':
                        break
                
                if host and path:
                    # 构建完整 URL
                    if path.startswith('http://') or path.startswith('https://'):
                        return path
                    else:
                        return f"http://{host}{path}"
                
                return None
                
            except Exception:
                return None
            
        except Exception:
            return None
    
    def _capture_loop(self) -> None:
        """捕获循环：拦截、检查进程、NAT 转发"""
        try:
            import pydivert

            # 设置 WinDivert DLL 路径
            dll_path = self._driver_manager.get_dll_path()
            if dll_path:
                # pydivert 会自动查找 DLL，但我们可以设置环境变量
                import os
                os.environ['PATH'] = str(dll_path.parent) + os.pathsep + os.environ.get('PATH', '')

            # 构建过滤规则
            filter_str = self._build_filter_string()
            logger.info(f"WinDivert filter: {filter_str}")

            # 打开 WinDivert 句柄
            with pydivert.WinDivert(filter_str) as w:
                self._handle = w
                self._state = CaptureState.RUNNING

                logger.info("WinDivert capture loop started")
                
                # 统计变量
                last_log_time = time.time()
                packets_since_last_log = 0
                redirected_since_last_log = 0

                while not self._stop_event.is_set():
                    try:
                        # 使用 wait 检查是否有数据包，避免无限阻塞
                        # pydivert 的 recv() 默认会阻塞，我们用 stop_event 来控制退出
                        if self._stop_event.wait(timeout=0.01):
                            break

                        # 接收数据包
                        packet = w.recv()

                        if packet is None:
                            continue

                        packets_since_last_log += 1

                        # 更新统计
                        with self._lock:
                            self._statistics.packets_intercepted += 1

                        # 快速检查：如果目标 IP 不在我们的列表中，立即转发
                        # 这样可以避免影响其他网络流量
                        dst_ip = packet.dst_addr
                        is_target_ip = False
                        
                        with self._lock:
                            # 检查是否是目标 IP
                            if dst_ip in self._target_ips:
                                is_target_ip = True
                            else:
                                # 检查是否匹配已知的 IP 前缀
                                for prefix in self._known_ip_prefixes:
                                    if dst_ip.startswith(prefix):
                                        is_target_ip = True
                                        break
                        
                        # 如果不是目标 IP，立即转发，不做任何处理
                        if not is_target_ip:
                            w.send(packet)
                            continue
                        
                        # 检查是否需要拦截（使用缓存，非阻塞）
                        should_redirect = self._should_intercept_fast(packet)
                        
                        # 调试：记录拦截决策
                        if packets_since_last_log < 5:  # 只记录前几个包
                            logger.info(f"Packet: {packet.src_addr}:{packet.src_port} -> {packet.dst_addr}:{packet.dst_port}, should_redirect={should_redirect}")
                        
                        if should_redirect:
                            # 被动嗅探模式：提取 SNI 或 HTTP URL，不修改流量
                            if self.PASSIVE_MODE:
                                # 尝试从 TCP 负载中提取信息
                                try:
                                    payload = bytes(packet.payload) if hasattr(packet, 'payload') else b''
                                    dst_ip = packet.dst_addr
                                    dst_port = packet.dst_port
                                    
                                    if payload:
                                        # 首先尝试提取 HTTP URL（80 端口）
                                        if dst_port == 80:
                                            http_url = self.extract_http_url(payload)
                                            if http_url:
                                                # 检查是否是视频号相关的 URL
                                                if self._is_video_url(http_url):
                                                    logger.info(f"Detected video URL: {http_url}")
                                                    
                                                    # 记录 URL
                                                    with self._sni_lock:
                                                        url_key = f"url:{http_url[:100]}"
                                                        if url_key not in self._detected_snis:
                                                            self._detected_snis[url_key] = datetime.now()
                                                            
                                                            # 触发回调，传递完整 URL
                                                            if self._on_sni_detected:
                                                                try:
                                                                    self._on_sni_detected(http_url, dst_ip, dst_port)
                                                                except Exception:
                                                                    pass
                                                    
                                                    # 更新统计
                                                    with self._lock:
                                                        self._statistics.connections_redirected += 1
                                                    redirected_since_last_log += 1
                                                else:
                                                    logger.debug(f"Non-video HTTP URL: {http_url[:80]}")
                                        
                                        # 然后尝试提取 TLS SNI（443 端口）
                                        elif dst_port == 443:
                                            sni = self.extract_sni_from_tls(payload)
                                            if sni:
                                                # 记录所有检测到的 SNI（调试用）
                                                logger.debug(f"Extracted SNI: {sni} -> {dst_ip}:{dst_port}")
                                                
                                                # 检查是否是视频号相关的 SNI
                                                if self._is_video_sni(sni):
                                                    logger.info(f"Detected video SNI: {sni} -> {dst_ip}:{dst_port}")
                                                    
                                                    # 记录 SNI
                                                    with self._sni_lock:
                                                        if sni not in self._detected_snis:
                                                            self._detected_snis[sni] = datetime.now()
                                                            
                                                            # 触发回调
                                                            if self._on_sni_detected:
                                                                try:
                                                                    self._on_sni_detected(sni, dst_ip, dst_port)
                                                                except Exception:
                                                                    pass
                                                    
                                                    # 更新统计
                                                    with self._lock:
                                                        self._statistics.connections_redirected += 1
                                                    redirected_since_last_log += 1
                                                else:
                                                    # 记录非视频号的 SNI（调试用）
                                                    logger.debug(f"Non-video SNI: {sni}")
                                            else:
                                                # 没有 SNI（可能是 ECH 加密），通过 IP 识别
                                                # 检查是否是 TLS ClientHello
                                                if len(payload) > 5 and payload[0] == 0x16 and payload[5] == 0x01:
                                                    # 检查是否是视频号相关的 IP
                                                    if self._is_video_ip(dst_ip):
                                                        logger.info(f"Detected video IP (no SNI/ECH): {dst_ip}:{dst_port}")
                                                        
                                                        # 使用 IP 作为标识
                                                        ip_key = f"ip:{dst_ip}"
                                                        with self._sni_lock:
                                                            if ip_key not in self._detected_snis:
                                                                self._detected_snis[ip_key] = datetime.now()
                                                                
                                                                # 触发回调，使用 IP 作为 SNI
                                                                if self._on_sni_detected:
                                                                    try:
                                                                        self._on_sni_detected(ip_key, dst_ip, dst_port)
                                                                    except Exception:
                                                                        pass
                                                        
                                                        # 更新统计
                                                        with self._lock:
                                                            self._statistics.connections_redirected += 1
                                                        redirected_since_last_log += 1
                                except Exception as e:
                                    logger.debug(f"Error extracting SNI: {e}")
                            else:
                                # NAT 模式：转发到本地代理
                                self._redirect_packet(packet)
                                redirected_since_last_log += 1

                                with self._lock:
                                    self._statistics.connections_redirected += 1

                        # 重新注入数据包（被动模式下不修改）
                        w.send(packet)
                        
                        # 每 5 秒输出一次统计日志
                        current_time = time.time()
                        if current_time - last_log_time >= 5:
                            logger.info(f"Capture stats (last 5s): packets={packets_since_last_log}, redirected={redirected_since_last_log}")
                            with self._process_cache_lock:
                                target_ports_count = len(self._target_process_ports)
                            with self._lock:
                                target_ips_count = len(self._target_ips)
                            logger.info(f"Cache status: target_ports={target_ports_count}, target_ips={target_ips_count}")
                            packets_since_last_log = 0
                            redirected_since_last_log = 0
                            last_log_time = current_time

                    except OSError as e:
                        if self._stop_event.is_set():
                            break
                        logger.warning(f"WinDivert recv error: {e}")
                    except Exception as e:
                        if self._stop_event.is_set():
                            break
                        logger.exception(f"Error in capture loop: {e}")

                logger.info("WinDivert capture loop ended")

                # with 块会自动关闭 handle，所以清空引用
                self._handle = None

        except ImportError:
            self._state = CaptureState.ERROR
            self._error_code = ErrorCode.DRIVER_MISSING
            self._error_message = "pydivert 模块未安装"
            logger.error("pydivert module not installed")
        except Exception as e:
            self._state = CaptureState.ERROR
            self._error_code = ErrorCode.CAPTURE_FAILED
            self._error_message = str(e)
            logger.exception("WinDivert capture error")
        finally:
            # 确保清空 handle 引用
            self._handle = None
    
    def _process_cache_loop(self) -> None:
        """后台线程：定期刷新进程端口缓存
        
        这个线程在后台运行，定期扫描系统连接并更新缓存，
        避免在数据包处理路径上调用慢速的 psutil.net_connections()
        """
        logger.info("Process cache loop started")
        
        while not self._stop_event.is_set():
            try:
                self._refresh_process_cache()
            except Exception as e:
                logger.debug(f"Error refreshing process cache: {e}")
            
            # 等待下一次刷新
            if self._stop_event.wait(timeout=PROCESS_CACHE_REFRESH_INTERVAL):
                break
        
        logger.info("Process cache loop ended")
    
    def _quic_block_loop(self) -> None:
        """QUIC 阻止循环：丢弃 UDP 443 流量
        
        微信视频号优先使用 QUIC 协议（UDP 443），这会绕过我们的 TCP 代理。
        通过阻止 UDP 443 流量，强制微信回退到 HTTPS (TCP 443)。
        """
        try:
            import pydivert
            
            # 构建 QUIC 阻止过滤规则：出站 UDP 到 443 端口
            # 只阻止目标进程的 QUIC 流量
            filter_str = "outbound and udp.DstPort == 443"
            
            logger.info(f"QUIC block filter: {filter_str}")
            
            with pydivert.WinDivert(filter_str) as w:
                self._quic_block_handle = w
                
                logger.info("QUIC blocking loop started")
                
                while not self._stop_event.is_set():
                    try:
                        if self._stop_event.wait(timeout=0.01):
                            break
                        
                        # 接收 UDP 包
                        packet = w.recv()
                        
                        if packet is None:
                            continue
                        
                        # 检查是否是目标进程的流量
                        if self._should_block_quic(packet):
                            # 丢弃包（不重新注入）
                            logger.debug(f"Blocked QUIC: {packet.src_addr}:{packet.src_port} -> {packet.dst_addr}:{packet.dst_port}")
                            continue
                        
                        # 非目标进程的 UDP 流量，正常放行
                        w.send(packet)
                        
                    except OSError as e:
                        if self._stop_event.is_set():
                            break
                        logger.warning(f"QUIC block recv error: {e}")
                    except Exception as e:
                        if self._stop_event.is_set():
                            break
                        logger.debug(f"Error in QUIC block loop: {e}")
                
                logger.info("QUIC blocking loop ended")
                self._quic_block_handle = None
                
        except ImportError:
            logger.warning("pydivert not available, QUIC blocking disabled")
        except Exception as e:
            logger.warning(f"QUIC blocking failed: {e}")
        finally:
            self._quic_block_handle = None
    
    def _should_block_quic(self, packet) -> bool:
        """判断是否应该阻止此 QUIC 包
        
        Args:
            packet: WinDivert UDP 数据包
            
        Returns:
            应该阻止返回 True
        """
        if not self.target_processes:
            # 没有指定进程，阻止所有目标 IP 的 QUIC
            with self._lock:
                dst_ip = packet.dst_addr
                return dst_ip in self._target_ips
        
        # 检查是否是目标进程
        src_port = packet.src_port
        
        with self._process_cache_lock:
            if src_port in self._target_process_ports:
                return True
        
        return False
    
    def _proxy_monitor_loop(self) -> None:
        """代理软件连接监控循环
        
        监控代理软件（如 Clash）的出站连接，通过 IP 地址识别视频流量。
        这是为了解决 ECH（加密 SNI）场景下无法提取 SNI 的问题。
        """
        try:
            import psutil
            
            logger.info("Proxy monitor loop started")
            
            # 查找代理进程
            proxy_pids = set()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = proc.info['name'].lower() if proc.info['name'] else ""
                    for proxy_name in self._proxy_processes:
                        if proxy_name in name:
                            proxy_pids.add(proc.info['pid'])
                            logger.info(f"Found proxy process: {proc.info['name']} (PID: {proc.info['pid']})")
                            break
                except:
                    pass
            
            if not proxy_pids:
                logger.info("No proxy processes found, proxy monitor disabled")
                return
            
            seen_ips = set()
            
            while not self._stop_event.is_set():
                try:
                    # 获取代理进程的 443 连接
                    for conn in psutil.net_connections(kind='tcp'):
                        if conn.pid in proxy_pids and conn.raddr:
                            remote_ip = conn.raddr.ip
                            remote_port = conn.raddr.port
                            
                            # 只关注 443 端口，排除 Fake-IP
                            if remote_port == 443 and not remote_ip.startswith("198.18."):
                                if remote_ip not in seen_ips:
                                    seen_ips.add(remote_ip)
                                    
                                    # 检查是否是视频号相关的 IP
                                    if self._is_video_ip(remote_ip):
                                        logger.info(f"Proxy monitor: detected video IP {remote_ip}")
                                        
                                        # 记录为检测到的 SNI（使用 IP 作为标识）
                                        ip_key = f"proxy:{remote_ip}"
                                        with self._sni_lock:
                                            if ip_key not in self._detected_snis:
                                                self._detected_snis[ip_key] = datetime.now()
                                                
                                                # 触发回调
                                                if self._on_sni_detected:
                                                    try:
                                                        self._on_sni_detected(ip_key, remote_ip, remote_port)
                                                    except Exception:
                                                        pass
                                        
                                        # 更新统计
                                        with self._lock:
                                            self._statistics.connections_redirected += 1
                    
                except Exception as e:
                    logger.debug(f"Error in proxy monitor: {e}")
                
                # 每 2 秒检查一次
                if self._stop_event.wait(timeout=2):
                    break
            
            logger.info("Proxy monitor loop ended")
            
        except ImportError:
            logger.warning("psutil not available, proxy monitor disabled")
        except Exception as e:
            logger.warning(f"Proxy monitor failed: {e}")
    
    def _is_video_sni(self, sni: str) -> bool:
        """检查 SNI 是否是视频号相关的域名
        
        使用 VideoURLExtractor 进行统一的URL模式匹配。
        
        Args:
            sni: SNI 域名
            
        Returns:
            如果是视频号相关域名返回 True
        """
        if not sni:
            return False
        
        # 使用 VideoURLExtractor 进行检查
        # 构建一个临时URL来检查
        test_url = f"https://{sni}/"
        if self._video_url_extractor.is_video_url(test_url):
            return True
        
        sni_lower = sni.lower()
        
        # 视频号相关的域名关键词（扩展版）
        video_keywords = [
            'finder',
            'video.qq.com',
            'video.wechat.com',
            'channels.weixin',
            'mpvideo.qpic.cn',
            'wxsnsdy',
            'wxsnsdythumb',
            'findermp',
            'findervideodownload',
            'finderlivevideo',
            'finderim',
            # 小程序视频（关键！）
            'wxapp.tc.qq.com',
            'stodownload',
            # 腾讯视频 CDN
            '.tc.qq.com',
            'vd.video.qq.com',
            'vd2.video.qq.com',
            'vd3.video.qq.com',
            'apdcdn.tc.qq.com',
        ]
        
        for keyword in video_keywords:
            if keyword in sni_lower:
                return True
        
        # 检查是否在目标域名列表中
        for domain in self.target_domains:
            if domain.lower() in sni_lower or sni_lower in domain.lower():
                return True
        
        return False
    
    def _is_video_url(self, url: str) -> bool:
        """检查 HTTP URL 是否是视频号相关的视频下载链接
        
        使用 VideoURLExtractor 进行统一的URL模式匹配。
        
        微信视频号的视频实际上通过 HTTP 80 端口下载，URL 格式如：
        http://wxapp.tc.qq.com/251/20302/stodownload?encfilekey=...
        
        Args:
            url: HTTP URL
            
        Returns:
            如果是视频号相关 URL 返回 True
        """
        if not url:
            return False
        
        # 使用 VideoURLExtractor 进行检查
        return self._video_url_extractor.is_video_url(url)
    
    def _is_video_ip(self, ip: str) -> bool:
        """检查 IP 是否是视频号相关的服务器
        
        使用 ECHHandler 进行IP识别，处理ECH加密场景。
        
        Args:
            ip: 目标 IP 地址
            
        Returns:
            如果是视频号相关 IP 返回 True
        """
        if not ip:
            return False
        
        # 检查是否在已解析的目标 IP 列表中
        with self._lock:
            if ip in self._target_ips:
                return True
        
        # 使用 ECHHandler 检查是否是腾讯CDN IP
        if self._ech_handler.is_video_server_ip(ip):
            return True
        
        # 检查是否是 Fake-IP（代理软件模式）
        if ip.startswith("198.18.") or ip.startswith("198.19."):
            with self._lock:
                if ip in self._target_ips:
                    return True
            return False
        
        # 检查是否匹配已知的腾讯视频 CDN IP 前缀
        tencent_video_prefixes = [
            # 腾讯云视频 CDN
            "101.89.", "101.91.", "101.226.", "101.227.",
            "183.47.", "183.60.", "183.131.", "183.136.",
            "180.163.", "180.153.", "180.101.", "180.102.", "180.110.", "180.111.",
            "119.147.", "119.167.",
            "113.96.", "113.105.", "113.108.", "113.240.",
            "14.17.", "14.18.", "14.29.",
            "125.39.",
            "58.250.", "58.251.",
            "59.36.", "59.37.",
            "61.147.", "61.151.",
            "121.51.",
            "140.207.",
            "182.254.",
            "211.152.",
            "223.167.",
            "117.21.", "117.62.", "117.89.",
            "124.225.", "124.95.",
            "122.246.", "122.247.",
            "115.150.", "115.223.", "115.227.",
            "114.80.", "114.230.",
            "150.138.",
            "175.4.",
            "112.64.",
            "120.53.",
            "42.192.",
            "106.38.",
        ]
        
        for prefix in tencent_video_prefixes:
            if ip.startswith(prefix):
                return True
        
        return False
    
    def _extract_video_from_url(self, url: str, dst_ip: str, dst_port: int) -> Optional[ExtractedVideo]:
        """从URL提取视频信息并去重
        
        使用 VideoURLExtractor 进行统一处理。
        
        Args:
            url: 视频URL
            dst_ip: 目标IP
            dst_port: 目标端口
            
        Returns:
            ExtractedVideo 对象，如果已存在或无效则返回 None
        """
        video = self._video_url_extractor.extract_and_deduplicate(url, "http")
        if video:
            # 触发回调
            if self._on_video_extracted:
                try:
                    self._on_video_extracted(video)
                except Exception:
                    pass
            
            # 更新统计
            with self._lock:
                self._statistics.videos_detected += 1
        
        return video
    
    def _handle_ech_connection(self, payload: bytes, dst_ip: str, dst_port: int) -> bool:
        """处理可能的ECH加密连接
        
        使用 ECHHandler 检测ECH并进行IP-based识别。
        
        Args:
            payload: TLS ClientHello数据
            dst_ip: 目标IP
            dst_port: 目标端口
            
        Returns:
            是否检测到视频相关连接
        """
        # 使用 ECHHandler 识别连接
        result = self._ech_handler.identify_connection(payload, dst_ip)
        
        if result["has_ech"]:
            # 更新ECH统计
            with self._lock:
                self._statistics.ech_detected += 1
            logger.debug(f"ECH detected for {dst_ip}:{dst_port}")
        
        if result["identified"]:
            if result["method"] == "sni" and result["sni"]:
                # 通过SNI识别
                return self._is_video_sni(result["sni"])
            elif result["method"] == "ip" and result["is_video_ip"]:
                # 通过IP识别（ECH场景）
                logger.info(f"Video IP identified via ECH fallback: {dst_ip}")
                return True
        
        return False
    
    def _is_wechat_port_fast(self, port: int) -> bool:
        """快速检查端口是否属于微信进程
        
        使用 WeChatProcessManager 的缓存进行快速查找。
        
        Args:
            port: 端口号
            
        Returns:
            是否属于微信进程
        """
        return self._wechat_process_manager.is_wechat_port(port)
    
    def get_detected_snis(self) -> List[str]:
        """获取检测到的 SNI 列表
        
        Returns:
            SNI 列表
        """
        with self._sni_lock:
            return list(self._detected_snis.keys())
    
    def clear_detected_snis(self) -> None:
        """清空检测到的 SNI 列表"""
        with self._sni_lock:
            self._detected_snis.clear()
    
    def _refresh_process_cache(self) -> None:
        """刷新进程端口缓存"""
        try:
            import psutil
            
            new_target_ports = set()
            new_cache = {}
            current_time = time.time()
            
            # 获取目标进程名列表（小写）
            target_names_lower = [p.lower() for p in self.target_processes]
            
            # 先获取所有目标进程的 PID
            target_pids = set()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and proc_name.lower() in target_names_lower:
                        target_pids.add(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # 扫描所有网络连接（包括 TCP 和 UDP）
            try:
                connections = psutil.net_connections(kind='inet')
            except psutil.AccessDenied:
                # 如果没有权限，尝试只获取 TCP 连接
                logger.warning("Access denied for net_connections, trying tcp only")
                try:
                    connections = psutil.net_connections(kind='tcp')
                except psutil.AccessDenied:
                    logger.warning("Access denied for tcp connections too")
                    connections = []
            
            for conn in connections:
                if conn.laddr and conn.pid:
                    port = conn.laddr.port
                    try:
                        proc = psutil.Process(conn.pid)
                        proc_name = proc.name()
                        new_cache[port] = (proc_name, current_time)
                        
                        # 检查是否是目标进程（通过 PID 或进程名）
                        if conn.pid in target_pids or proc_name.lower() in target_names_lower:
                            new_target_ports.add(port)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # 如果无法获取进程信息，但 PID 在目标列表中，也添加端口
                        if conn.pid in target_pids:
                            new_target_ports.add(port)
            
            # 原子更新缓存
            with self._process_cache_lock:
                self._process_port_cache = new_cache
                self._target_process_ports = new_target_ports
            
            # 输出详细日志
            logger.info(f"Process cache refreshed: {len(new_target_ports)} target ports, {len(target_pids)} target PIDs, {len(connections)} total connections")
            if new_target_ports:
                # 显示前 30 个端口
                ports_preview = sorted(list(new_target_ports))[:30]
                logger.info(f"Target process ports: {ports_preview}{'...' if len(new_target_ports) > 30 else ''}")
            elif target_pids:
                logger.info(f"Found {len(target_pids)} target PIDs but no active network connections")
            else:
                logger.warning(f"No target process ports found! Looking for: {self.target_processes}")
            
        except Exception as e:
            logger.warning(f"Error in _refresh_process_cache: {e}")
    
    def _should_intercept_fast(self, packet) -> bool:
        """快速判断是否应该拦截此数据包（使用缓存）
        
        使用 WeChatProcessManager 进行快速进程过滤。
        
        Args:
            packet: WinDivert 数据包
            
        Returns:
            应该拦截返回 True
        """
        # 获取目标 IP 和端口
        dst_ip = packet.dst_addr
        dst_port = packet.dst_port
        
        # 排除本地回环地址
        if dst_ip.startswith("127."):
            return False
        
        # 排除私有地址（除非是 Fake-IP）
        if dst_ip.startswith("192.168.") or dst_ip.startswith("10."):
            return False
        
        # 对于 80 端口，总是尝试提取 HTTP URL
        if dst_port == 80:
            return True
        
        # 对于 443 端口，检查是否是目标 IP
        with self._lock:
            is_target_ip = dst_ip in self._target_ips
            
            # 如果不在精确列表中，检查是否匹配已知的腾讯 IP 前缀
            if not is_target_ip and hasattr(self, '_known_ip_prefixes'):
                is_target_ip = any(dst_ip.startswith(prefix) for prefix in self._known_ip_prefixes)
            
            # 检查是否是 Fake-IP（代理软件模式）
            if not is_target_ip:
                is_fake_ip = dst_ip.startswith("198.18.") or dst_ip.startswith("198.19.")
                if is_fake_ip:
                    is_target_ip = True
            
            # 使用 ECHHandler 检查是否是腾讯CDN IP
            if not is_target_ip:
                is_target_ip = self._ech_handler.is_video_server_ip(dst_ip)
            
            # 检查是否是腾讯视频 CDN IP（备用）
            if not is_target_ip:
                is_target_ip = self._is_video_ip(dst_ip)
        
        return is_target_ip
    
    def _should_intercept(self, packet) -> bool:
        """判断是否应该拦截此数据包（兼容旧接口，使用快速版本）
        
        Args:
            packet: WinDivert 数据包
            
        Returns:
            应该拦截返回 True
        """
        return self._should_intercept_fast(packet)

    def _redirect_packet(self, packet) -> None:
        """NAT 转发数据包到本地代理

        Args:
            packet: WinDivert 数据包
        """
        try:
            # 记录原始目的地
            original_dst = (packet.dst_addr, packet.dst_port)
            connection_key = (packet.src_addr, packet.src_port, packet.dst_addr, packet.dst_port)

            with self._lock:
                if connection_key not in self._connection_table:
                    self._connection_table[connection_key] = original_dst
                    logger.info(f"NAT: {packet.src_addr}:{packet.src_port} -> "
                               f"{packet.dst_addr}:{packet.dst_port} => 127.0.0.1:{self.proxy_port}")
                self._connection_last_seen[connection_key] = datetime.now()
                self._prune_connections()

            # 修改目的地址为本地代理
            packet.dst_addr = "127.0.0.1"
            packet.dst_port = self.proxy_port

            # 触发回调
            if self._on_packet_intercepted:
                try:
                    self._on_packet_intercepted({
                        "src_addr": packet.src_addr,
                        "src_port": packet.src_port,
                        "original_dst_addr": original_dst[0],
                        "original_dst_port": original_dst[1],
                        "redirected_to": f"127.0.0.1:{self.proxy_port}",
                    })
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Error redirecting packet: {e}")
    
    def _restore_packet(self, packet) -> None:
        """恢复数据包的原始目的地（用于响应包）
        
        Args:
            packet: WinDivert 数据包
        """
        try:
            # 查找原始目的地
            # 对于响应包，源地址是代理，需要恢复为原始服务器
            connection_key = (packet.dst_addr, packet.dst_port, "127.0.0.1", self.proxy_port)
            
            with self._lock:
                original_dst = self._connection_table.get(connection_key)
            
            if original_dst:
                packet.src_addr = original_dst[0]
                packet.src_port = original_dst[1]
                
        except Exception as e:
            logger.debug(f"Error restoring packet: {e}")
    
    def get_connection_count(self) -> int:
        """获取当前跟踪的连接数
        
        Returns:
            连接数
        """
        with self._lock:
            return len(self._connection_table)
    
    def clear_statistics(self) -> None:
        """清空统计信息"""
        with self._lock:
            self._statistics = CaptureStatistics()
    
    def update_video_detected(self) -> None:
        """更新视频检测计数和时间戳"""
        with self._lock:
            self._statistics.videos_detected += 1
            self._statistics.last_detection_at = datetime.now()
    
    def add_unrecognized_domain(self, domain: str) -> None:
        """添加未识别的域名
        
        Args:
            domain: 域名
        """
        with self._lock:
            if domain not in self._statistics.unrecognized_domains:
                self._statistics.unrecognized_domains.append(domain)
                # 限制列表大小
                if len(self._statistics.unrecognized_domains) > 100:
                    self._statistics.unrecognized_domains = self._statistics.unrecognized_domains[-100:]

    def _prune_connections(self, max_age_seconds: int = 300) -> None:
        """清理过期的连接映射（需在锁内调用）"""
        cutoff = datetime.now()
        stale_keys = [
            key for key, ts in self._connection_last_seen.items()
            if (cutoff - ts).total_seconds() > max_age_seconds
        ]
        for key in stale_keys:
            self._connection_last_seen.pop(key, None)
            self._connection_table.pop(key, None)
    
    # ========================================
    # 新增：组件访问方法
    # ========================================
    
    def get_ech_handler(self) -> ECHHandler:
        """获取ECH处理器实例"""
        return self._ech_handler
    
    def get_video_url_extractor(self) -> VideoURLExtractor:
        """获取视频URL提取器实例"""
        return self._video_url_extractor
    
    def get_wechat_process_manager(self) -> WeChatProcessManager:
        """获取微信进程管理器实例"""
        return self._wechat_process_manager
    
    def get_extracted_video_count(self) -> int:
        """获取已提取的视频数量（去重后）"""
        return self._video_url_extractor.get_extracted_count()
    
    def is_wechat_running(self) -> bool:
        """检查微信是否在运行"""
        return self._wechat_process_manager.is_wechat_running()
    
    def get_wechat_port_count(self) -> int:
        """获取微信进程使用的端口数量"""
        return self._wechat_process_manager.get_port_count()
