"""
多模式嗅探器

统一管理多种捕获模式，提供自动切换和聚合。
支持WinDivert透明捕获、Clash API监控、系统代理拦截和混合模式。

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Set
from dataclasses import dataclass, field

from .models import (
    CaptureMode, CaptureState, CaptureStatus, CaptureStartResult,
    CaptureStatistics, ProxyType, ProxyMode, ProxyInfo,
    DetectedVideo, MultiModeCaptureConfig, ExtendedErrorCode,
    EncryptionType,
    get_extended_error_message,
)
from .proxy_detector import ProxyDetector
from .clash_api_monitor import ClashAPIMonitor, ClashConnection
from .video_url_extractor import VideoURLExtractor, ExtractedVideo
from .video_metadata_extractor import VideoMetadataExtractor, VideoMetadata
from .wechat_process_manager import WeChatProcessManager
from .recovery_manager import RecoveryManager
from .quic_manager import QUICManager
from .ech_handler import ECHHandler

logger = logging.getLogger(__name__)


@dataclass
class CaptureResult:
    """捕获结果"""
    mode: CaptureMode
    url: Optional[str]
    sni: Optional[str]
    dst_ip: str
    dst_port: int
    timestamp: datetime = field(default_factory=datetime.now)
    is_video: bool = False
    video_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "mode": self.mode.value,
            "url": self.url,
            "sni": self.sni,
            "dst_ip": self.dst_ip,
            "dst_port": self.dst_port,
            "timestamp": self.timestamp.isoformat(),
            "is_video": self.is_video,
            "video_id": self.video_id,
        }


class MultiModeSniffer:
    """多模式嗅探器
    
    统一管理多种捕获模式，提供自动切换和聚合。
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
    """
    
    # 模式回退链
    FALLBACK_CHAIN = [
        CaptureMode.WINDIVERT,
        CaptureMode.CLASH_API,
        CaptureMode.SYSTEM_PROXY,
    ]
    
    def __init__(
        self,
        config: Optional[MultiModeCaptureConfig] = None,
        on_video_detected: Optional[Callable[[DetectedVideo], None]] = None,
    ):
        """初始化多模式嗅探器
        
        Args:
            config: 捕获配置
            on_video_detected: 检测到视频时的回调
        """
        self._config = config or MultiModeCaptureConfig()
        self._on_video_detected = on_video_detected
        
        # 组件
        self._proxy_detector = ProxyDetector()
        self._clash_monitor: Optional[ClashAPIMonitor] = None
        self._video_extractor = VideoURLExtractor()
        self._metadata_extractor = VideoMetadataExtractor(timeout=10, max_retries=2)
        self._wechat_manager = WeChatProcessManager()
        self._recovery_manager = RecoveryManager(
            max_retries=self._config.max_recovery_attempts,
            backoff_base=self._config.recovery_backoff_base,
            backoff_max=self._config.recovery_backoff_max,
        )
        self._quic_manager = QUICManager(
            target_processes=self._config.target_processes,
        )
        self._ech_handler = ECHHandler()
        
        # 状态
        self._current_mode: CaptureMode = CaptureMode.HYBRID
        self._state: CaptureState = CaptureState.STOPPED
        self._detected_videos: List[DetectedVideo] = []
        self._statistics = CaptureStatistics()
        self._started_at: Optional[datetime] = None
        self._error_message: Optional[str] = None
        self._error_code: Optional[str] = None
        self._proxy_info: Optional[ProxyInfo] = None
        
        # 可用模式缓存
        self._available_modes: List[CaptureMode] = []
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 任务
        self._capture_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
        # 注册组件到恢复管理器
        self._register_components()
    
    def _register_components(self) -> None:
        """注册组件到恢复管理器"""
        self._recovery_manager.register_component(
            "clash_monitor",
            self._clash_monitor,
            health_check=lambda: self._clash_monitor is not None and self._clash_monitor.is_connected,
            recovery_func=self._recover_clash_monitor,
        )
        self._recovery_manager.register_component(
            "wechat_manager",
            self._wechat_manager,
            health_check=lambda: self._wechat_manager.is_monitoring,
        )
        self._recovery_manager.register_component(
            "quic_manager",
            self._quic_manager,
            health_check=lambda: True,  # QUIC manager is optional
        )
    
    async def _recover_clash_monitor(self) -> bool:
        """恢复Clash监控器"""
        try:
            if self._clash_monitor:
                await self._clash_monitor.disconnect()
            
            self._clash_monitor = ClashAPIMonitor(
                api_address=self._config.clash_api_address,
                api_secret=self._config.clash_api_secret,
            )
            return await self._clash_monitor.connect()
        except Exception as e:
            logger.error(f"Failed to recover Clash monitor: {e}")
            return False
    
    @property
    def current_mode(self) -> CaptureMode:
        """获取当前模式"""
        return self._current_mode
    
    @property
    def state(self) -> CaptureState:
        """获取当前状态"""
        return self._state
    
    @property
    def detected_videos(self) -> List[DetectedVideo]:
        """获取检测到的视频列表"""
        return self._detected_videos.copy()
    
    @property
    def statistics(self) -> CaptureStatistics:
        """获取统计信息"""
        return self._statistics
    
    async def start(self, mode: CaptureMode = CaptureMode.HYBRID) -> CaptureStartResult:
        """启动捕获
        
        Property 3: Capture Mode Auto-Selection
        对于任何检测到的代理环境，ModeSelector应选择兼容的捕获模式。
        当未检测到代理时，应选择WinDivert模式。
        当检测到Clash时，应优先选择Clash API模式。
        
        Args:
            mode: 捕获模式，HYBRID会自动选择
            
        Returns:
            启动结果
        """
        async with self._lock:
            if self._state in (CaptureState.RUNNING, CaptureState.STARTING):
                return CaptureStartResult(
                    success=False,
                    mode=self._current_mode,
                    error_message="Capture is already running",
                )
            
            self._state = CaptureState.STARTING
            self._error_message = None
            self._error_code = None
        
        try:
            # 检测代理环境
            self._proxy_info = await self._proxy_detector.detect()
            logger.info(f"Detected proxy: {self._proxy_info.proxy_type.value}, "
                       f"mode: {self._proxy_info.proxy_mode.value}")
            
            # 获取可用模式
            self._available_modes = await self._get_available_modes()
            
            # 选择捕获模式
            if mode == CaptureMode.HYBRID:
                selected_mode = await self._auto_select_mode()
            else:
                selected_mode = mode
            
            # 验证模式可用性
            if selected_mode not in self._available_modes:
                # 尝试回退
                selected_mode = await self._find_fallback_mode(selected_mode)
                if selected_mode is None:
                    async with self._lock:
                        self._state = CaptureState.ERROR
                        self._error_message = "No available capture mode"
                        self._error_code = ExtendedErrorCode.CAPTURE_FAILED
                    return CaptureStartResult(
                        success=False,
                        mode=mode,
                        error_message="No available capture mode",
                        error_code=ExtendedErrorCode.CAPTURE_FAILED,
                    )
            
            self._current_mode = selected_mode
            
            # 启动微信进程管理器
            self._wechat_manager.start_monitoring()
            
            # 根据模式启动相应的捕获
            success = await self._start_capture_mode(selected_mode)
            
            if success:
                # 启动QUIC阻止（如果配置启用）
                if self._config.quic_blocking_enabled:
                    await self._quic_manager.start_blocking()
                
                # 启动恢复管理器看门狗
                self._recovery_manager.start_watchdog()
                
                async with self._lock:
                    self._state = CaptureState.RUNNING
                    self._started_at = datetime.now()
                
                logger.info(f"Capture started in {selected_mode.value} mode")
                
                return CaptureStartResult(
                    success=True,
                    mode=selected_mode,
                )
            else:
                # 尝试回退
                fallback_result = await self._handle_mode_failure(selected_mode)
                if fallback_result:
                    return CaptureStartResult(
                        success=True,
                        mode=self._current_mode,
                    )
                
                async with self._lock:
                    self._state = CaptureState.ERROR
                
                return CaptureStartResult(
                    success=False,
                    mode=selected_mode,
                    error_message=self._error_message,
                    error_code=self._error_code,
                )
                
        except Exception as e:
            logger.error(f"Failed to start capture: {e}")
            async with self._lock:
                self._state = CaptureState.ERROR
                self._error_message = str(e)
            return CaptureStartResult(
                success=False,
                mode=mode,
                error_message=str(e),
            )
    
    async def stop(self) -> bool:
        """停止捕获
        
        Returns:
            是否成功停止
        """
        async with self._lock:
            if self._state == CaptureState.STOPPED:
                return True
            
            self._state = CaptureState.STOPPING
        
        try:
            # 停止捕获任务
            self._stop_event.set()
            if self._capture_task:
                self._capture_task.cancel()
                try:
                    await asyncio.wait_for(
                        asyncio.shield(self._capture_task),
                        timeout=2.0
                    )
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                self._capture_task = None
            
            # 停止各组件
            if self._clash_monitor:
                await self._clash_monitor.disconnect()
                self._clash_monitor = None
            
            await self._quic_manager.stop_blocking()
            self._wechat_manager.stop_monitoring()
            self._recovery_manager.stop_watchdog()
            
            # 关闭元数据提取器的 session
            await self._metadata_extractor.close()
            
            async with self._lock:
                self._state = CaptureState.STOPPED
                self._started_at = None
            
            logger.info("Capture stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping capture: {e}")
            async with self._lock:
                self._state = CaptureState.STOPPED
            return False
    
    async def switch_mode(self, new_mode: CaptureMode) -> bool:
        """切换捕获模式（保留视频）
        
        Property 4: Capture Mode Fallback Chain
        模式切换时应保留所有已检测的视频。
        
        Args:
            new_mode: 新模式
            
        Returns:
            是否成功切换
        """
        if new_mode == self._current_mode:
            return True
        
        if new_mode not in self._available_modes:
            logger.warning(f"Mode {new_mode.value} is not available")
            return False
        
        # 保留当前视频
        preserved_videos = self._detected_videos.copy()
        self._recovery_manager.preserve_videos(preserved_videos)
        
        logger.info(f"Switching mode from {self._current_mode.value} to {new_mode.value}, "
                   f"preserving {len(preserved_videos)} videos")
        
        # 停止当前模式
        await self._stop_capture_mode(self._current_mode)
        
        # 启动新模式
        success = await self._start_capture_mode(new_mode)
        
        if success:
            self._current_mode = new_mode
            # 恢复视频列表
            self._detected_videos = preserved_videos
            logger.info(f"Successfully switched to {new_mode.value} mode")
            return True
        else:
            # 回退到原模式
            logger.warning(f"Failed to switch to {new_mode.value}, reverting")
            await self._start_capture_mode(self._current_mode)
            self._detected_videos = preserved_videos
            return False
    
    def get_available_modes(self) -> List[CaptureMode]:
        """获取可用的捕获模式
        
        Returns:
            可用模式列表
        """
        return self._available_modes.copy()
    
    async def _get_available_modes(self) -> List[CaptureMode]:
        """获取可用的捕获模式（内部方法）
        
        Returns:
            可用模式列表
        """
        modes = []
        
        # HYBRID总是可用
        modes.append(CaptureMode.HYBRID)
        
        # 检查WinDivert
        if self._is_windivert_available():
            modes.append(CaptureMode.WINDIVERT)
        
        # 检查Clash API
        if self._proxy_info and self._proxy_info.proxy_type in (
            ProxyType.CLASH, ProxyType.CLASH_VERGE, ProxyType.CLASH_META
        ):
            modes.append(CaptureMode.CLASH_API)
        
        # 系统代理模式总是可用（作为后备）
        modes.append(CaptureMode.SYSTEM_PROXY)
        
        return modes
    
    def _is_windivert_available(self) -> bool:
        """检查WinDivert是否可用"""
        try:
            import pydivert
            return True
        except ImportError:
            return False
    
    async def _auto_select_mode(self) -> CaptureMode:
        """自动选择最佳模式
        
        Property 3: Capture Mode Auto-Selection
        
        Returns:
            选择的模式
        """
        if not self._proxy_info or self._proxy_info.proxy_type == ProxyType.NONE:
            # 无代理环境，优先使用WinDivert
            if CaptureMode.WINDIVERT in self._available_modes:
                logger.info("No proxy detected, selecting WinDivert mode")
                return CaptureMode.WINDIVERT
        
        # 检测到Clash系列代理
        if self._proxy_info.proxy_type in (
            ProxyType.CLASH, ProxyType.CLASH_VERGE, ProxyType.CLASH_META
        ):
            if CaptureMode.CLASH_API in self._available_modes:
                logger.info(f"Clash detected ({self._proxy_info.proxy_type.value}), "
                           f"selecting Clash API mode")
                return CaptureMode.CLASH_API
        
        # TUN模式下，WinDivert可能不工作
        if self._proxy_info.proxy_mode == ProxyMode.TUN:
            logger.warning("TUN mode detected, WinDivert may not work properly")
            if CaptureMode.CLASH_API in self._available_modes:
                return CaptureMode.CLASH_API
        
        # 默认使用WinDivert
        if CaptureMode.WINDIVERT in self._available_modes:
            return CaptureMode.WINDIVERT
        
        # 最后回退到系统代理
        return CaptureMode.SYSTEM_PROXY
    
    async def _find_fallback_mode(self, failed_mode: CaptureMode) -> Optional[CaptureMode]:
        """查找回退模式
        
        Args:
            failed_mode: 失败的模式
            
        Returns:
            回退模式，如果没有可用的则返回None
        """
        try:
            failed_index = self.FALLBACK_CHAIN.index(failed_mode)
        except ValueError:
            failed_index = -1
        
        # 从失败模式之后开始查找
        for mode in self.FALLBACK_CHAIN[failed_index + 1:]:
            if mode in self._available_modes:
                return mode
        
        return None

    async def _handle_mode_failure(self, failed_mode: CaptureMode) -> bool:
        """处理模式失败，尝试回退
        
        Property 4: Capture Mode Fallback Chain
        对于任何捕获模式失败，系统应尝试回退到链中的下一个可用模式
        (WinDivert → Clash API → System Proxy)，
        并在模式转换期间保留所有先前检测到的视频。
        
        Args:
            failed_mode: 失败的模式
            
        Returns:
            是否成功回退
        """
        if not self._config.auto_fallback:
            logger.info("Auto fallback is disabled")
            return False
        
        # 保留视频
        preserved_videos = self._detected_videos.copy()
        self._recovery_manager.preserve_videos(preserved_videos)
        
        logger.info(f"Mode {failed_mode.value} failed, attempting fallback")
        
        # 查找回退模式
        fallback_mode = await self._find_fallback_mode(failed_mode)
        
        if fallback_mode is None:
            logger.error("No fallback mode available")
            return False
        
        logger.info(f"Falling back to {fallback_mode.value} mode")
        
        # 尝试启动回退模式
        success = await self._start_capture_mode(fallback_mode)
        
        if success:
            self._current_mode = fallback_mode
            # 恢复视频
            self._detected_videos = preserved_videos
            logger.info(f"Successfully fell back to {fallback_mode.value} mode")
            return True
        else:
            # 继续尝试下一个回退模式
            return await self._handle_mode_failure(fallback_mode)
    
    async def _start_capture_mode(self, mode: CaptureMode) -> bool:
        """启动指定的捕获模式
        
        Args:
            mode: 捕获模式
            
        Returns:
            是否成功启动
        """
        try:
            if mode == CaptureMode.WINDIVERT:
                return await self._start_windivert_capture()
            elif mode == CaptureMode.CLASH_API:
                return await self._start_clash_api_capture()
            elif mode == CaptureMode.SYSTEM_PROXY:
                return await self._start_system_proxy_capture()
            elif mode == CaptureMode.HYBRID:
                # 混合模式：尝试自动选择
                selected = await self._auto_select_mode()
                return await self._start_capture_mode(selected)
            else:
                logger.error(f"Unknown capture mode: {mode}")
                return False
        except Exception as e:
            logger.error(f"Failed to start {mode.value} capture: {e}")
            self._error_message = str(e)
            return False
    
    async def _stop_capture_mode(self, mode: CaptureMode) -> None:
        """停止指定的捕获模式
        
        Args:
            mode: 捕获模式
        """
        try:
            if mode == CaptureMode.CLASH_API:
                if self._clash_monitor:
                    await self._clash_monitor.stop_polling()
                    await self._clash_monitor.disconnect()
                    self._clash_monitor = None
            # WinDivert和System Proxy的停止在stop()中统一处理
        except Exception as e:
            logger.error(f"Error stopping {mode.value} capture: {e}")
    
    async def _start_windivert_capture(self) -> bool:
        """启动WinDivert捕获
        
        Returns:
            是否成功启动
        """
        try:
            import pydivert
            
            # 这里只是验证WinDivert可用
            # 实际的WinDivert捕获逻辑在traffic_capture.py中
            logger.info("WinDivert capture mode initialized")
            
            # 启动捕获任务
            self._stop_event.clear()
            self._capture_task = asyncio.create_task(self._windivert_capture_loop())
            
            return True
            
        except ImportError:
            logger.error("pydivert not available")
            self._error_message = "WinDivert driver not installed"
            self._error_code = ExtendedErrorCode.DRIVER_MISSING
            return False
        except Exception as e:
            logger.error(f"Failed to start WinDivert capture: {e}")
            self._error_message = str(e)
            return False
    
    async def _windivert_capture_loop(self) -> None:
        """WinDivert捕获循环
        
        注意：这是一个简化的实现，实际的WinDivert捕获逻辑
        应该集成现有的traffic_capture.py模块。
        """
        try:
            import pydivert
            
            # 创建WinDivert过滤器
            filter_str = "tcp.DstPort == 443 and outbound"
            
            with pydivert.WinDivert(filter_str) as w:
                while not self._stop_event.is_set():
                    try:
                        # 设置超时以便检查停止事件
                        packet = w.recv()
                        
                        if packet:
                            # 重新注入包
                            w.send(packet)
                            
                            # 分析包
                            await self._analyze_packet(packet)
                            
                            self._statistics.packets_intercepted += 1
                        
                        # 让出控制权
                        await asyncio.sleep(0)
                        
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        if not self._stop_event.is_set():
                            logger.error(f"Error in WinDivert capture loop: {e}")
                        await asyncio.sleep(0.1)
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"WinDivert capture loop error: {e}")
            # 尝试恢复
            if self._state == CaptureState.RUNNING:
                await self._recovery_manager.attempt_recovery(
                    "windivert_capture",
                    Exception(str(e))
                )
    
    async def _analyze_packet(self, packet: Any) -> None:
        """分析捕获的包
        
        Args:
            packet: WinDivert包
        """
        try:
            # 检查是否是微信进程的流量
            src_port = packet.src_port
            if not self._wechat_manager.is_wechat_port(src_port):
                return
            
            dst_ip = packet.dst_addr
            dst_port = packet.dst_port
            
            # 尝试提取SNI
            payload = packet.payload
            if payload and len(payload) > 5:
                # 检查是否是TLS ClientHello
                if payload[0] == 0x16:  # TLS Handshake
                    sni = self._extract_sni(payload)
                    
                    if sni:
                        self._statistics.snis_extracted += 1
                        
                        # 检查是否是视频URL
                        video = self._video_extractor.extract_from_sni(sni, dst_ip)
                        if video:
                            await self._handle_detected_video(video)
                    else:
                        # 可能是ECH加密
                        if self._ech_handler.has_ech_extension(payload):
                            self._statistics.ech_detected += 1
                            
                            # 使用IP回退
                            if self._ech_handler.is_video_server_ip(dst_ip):
                                video = ExtractedVideo(
                                    url=f"https://{dst_ip}/",
                                    video_id=f"ip_{dst_ip}_{dst_port}",
                                    source="ip",
                                    domain=dst_ip,
                                )
                                await self._handle_detected_video(video)
            
        except Exception as e:
            logger.debug(f"Error analyzing packet: {e}")
    
    def _extract_sni(self, payload: bytes) -> Optional[str]:
        """从TLS ClientHello中提取SNI
        
        Args:
            payload: TLS数据
            
        Returns:
            SNI，如果无法提取则返回None
        """
        try:
            # 简化的SNI提取
            # TLS Record: type(1) + version(2) + length(2) + data
            if len(payload) < 5:
                return None
            
            if payload[0] != 0x16:  # Not Handshake
                return None
            
            # 查找SNI扩展
            # SNI扩展类型: 0x00 0x00
            sni_marker = b'\x00\x00'
            idx = payload.find(sni_marker, 40)  # 跳过固定头部
            
            while idx != -1 and idx < len(payload) - 10:
                # 检查是否是SNI扩展
                ext_type = payload[idx:idx+2]
                if ext_type == b'\x00\x00':
                    # 读取扩展长度
                    ext_len = int.from_bytes(payload[idx+2:idx+4], 'big')
                    if idx + 4 + ext_len <= len(payload):
                        # 读取SNI列表长度
                        sni_list_len = int.from_bytes(payload[idx+4:idx+6], 'big')
                        # 读取SNI类型（应该是0x00表示hostname）
                        if payload[idx+6] == 0x00:
                            # 读取hostname长度
                            hostname_len = int.from_bytes(payload[idx+7:idx+9], 'big')
                            if idx + 9 + hostname_len <= len(payload):
                                hostname = payload[idx+9:idx+9+hostname_len].decode('ascii', errors='ignore')
                                return hostname
                
                idx = payload.find(sni_marker, idx + 1)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting SNI: {e}")
            return None
    
    async def _start_clash_api_capture(self) -> bool:
        """启动Clash API捕获
        
        Returns:
            是否成功启动
        """
        try:
            # 获取API地址
            api_address = self._config.clash_api_address
            api_secret = self._config.clash_api_secret
            
            # 如果配置为空，尝试从代理信息获取
            if not api_address and self._proxy_info:
                api_address = self._proxy_info.api_address or "127.0.0.1:9090"
                api_secret = self._proxy_info.api_secret or ""
            
            # 创建监控器
            self._clash_monitor = ClashAPIMonitor(
                api_address=api_address,
                api_secret=api_secret,
            )
            
            # 连接
            if not await self._clash_monitor.connect():
                self._error_message = "Failed to connect to Clash API"
                self._error_code = ExtendedErrorCode.CLASH_API_FAILED
                return False
            
            # 启动轮询
            await self._clash_monitor.start_polling(
                interval=1.0,
                callback=self._on_clash_connection,
            )
            
            logger.info(f"Clash API capture started, connected to {api_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Clash API capture: {e}")
            self._error_message = str(e)
            self._error_code = ExtendedErrorCode.CLASH_API_FAILED
            return False
    
    def _on_clash_connection(self, conn: ClashConnection) -> None:
        """Clash连接回调
        
        Args:
            conn: Clash连接
        """
        try:
            self._statistics.connections_analyzed += 1
            
            # 提取视频信息
            video = self._video_extractor.extract_from_clash_connection(conn)
            if video:
                # 使用asyncio.create_task在事件循环中处理
                asyncio.create_task(self._handle_detected_video(video))
                
        except Exception as e:
            logger.error(f"Error handling Clash connection: {e}")
    
    async def _start_system_proxy_capture(self) -> bool:
        """启动系统代理捕获
        
        Returns:
            是否成功启动
        """
        # 系统代理模式的实现依赖于现有的proxy_sniffer.py
        # 这里只是标记模式已启动
        logger.info("System proxy capture mode initialized")
        return True

    async def _handle_detected_video(self, video: ExtractedVideo) -> None:
        """处理检测到的视频
        
        Args:
            video: 提取的视频信息
        """
        # 检查是否已存在（去重）
        existing_ids = {v.id for v in self._detected_videos}
        if video.video_id in existing_ids:
            return
        
        # 异步提取元数据
        metadata: Optional[VideoMetadata] = None
        try:
            # 尝试提取元数据（不使用 yt-dlp，因为微信视频号不支持）
            metadata = await self._metadata_extractor.extract_comprehensive(
                url=video.url,
                try_ytdlp=False,  # 微信视频号不支持 yt-dlp
                http_response=None,
            )
            
            if metadata:
                logger.info(f"Extracted metadata: title={metadata.title}, filesize={metadata.filesize}, resolution={metadata.resolution}")
        except Exception as e:
            logger.warning(f"Failed to extract metadata for {video.video_id}: {e}")
        
        # 创建DetectedVideo对象，优先使用提取的元数据
        detected = DetectedVideo(
            id=video.video_id,
            url=video.url,
            detected_at=video.detected_at,
            title=metadata.title if metadata and metadata.title else f"视频 {video.video_id[:8]}",
            thumbnail=metadata.thumbnail if metadata else None,
            duration=metadata.duration if metadata else None,
            resolution=metadata.resolution if metadata else video.quality,
            filesize=metadata.filesize if metadata else video.filesize,
            encryption_type=EncryptionType.UNKNOWN if not video.is_encrypted else EncryptionType.UNKNOWN,
            decryption_key=video.decryption_key,
        )
        
        self._detected_videos.append(detected)
        self._statistics.videos_detected += 1
        self._statistics.last_detection_at = datetime.now()
        
        logger.info(f"Video detected: {video.video_id} from {video.source}, title={detected.title}")
        
        # 调用回调
        if self._on_video_detected:
            try:
                self._on_video_detected(detected)
            except Exception as e:
                logger.error(f"Error in video detected callback: {e}")
    
    def get_status(self) -> CaptureStatus:
        """获取捕获状态
        
        Returns:
            捕获状态
        """
        return CaptureStatus(
            state=self._state,
            mode=self._current_mode,
            statistics=self._statistics,
            started_at=self._started_at,
            error_message=self._error_message,
            error_code=self._error_code,
            proxy_info=self._proxy_info,
            available_modes=self._available_modes,
        )
    
    def clear_videos(self) -> None:
        """清除检测到的视频列表"""
        self._detected_videos.clear()
        self._video_extractor.clear_extracted_ids()
        self._statistics.videos_detected = 0
    
    def get_video_count(self) -> int:
        """获取检测到的视频数量"""
        return len(self._detected_videos)
    
    async def toggle_quic_blocking(self, enabled: bool) -> bool:
        """切换QUIC阻止
        
        Args:
            enabled: 是否启用
            
        Returns:
            是否成功切换
        """
        if enabled:
            success = await self._quic_manager.start_blocking()
            if success:
                self._config.quic_blocking_enabled = True
            return success
        else:
            success = await self._quic_manager.stop_blocking()
            if success:
                self._config.quic_blocking_enabled = False
            return success
    
    def is_quic_blocking_enabled(self) -> bool:
        """QUIC阻止是否启用"""
        return self._quic_manager.is_blocking
    
    def get_quic_blocked_count(self) -> int:
        """获取QUIC阻止的包数量"""
        return self._quic_manager.get_blocked_count()
    
    def get_recovery_history(self) -> List[Dict[str, Any]]:
        """获取恢复历史
        
        Returns:
            恢复历史列表
        """
        return [a.to_dict() for a in self._recovery_manager.get_recovery_history()]
    
    def get_errors_recovered_count(self) -> int:
        """获取成功恢复的错误数量"""
        return self._recovery_manager.get_errors_recovered_count()
    
    def update_config(self, config: MultiModeCaptureConfig) -> None:
        """更新配置
        
        Args:
            config: 新配置
        """
        self._config = config
        
        # 更新组件配置
        self._quic_manager.target_processes = config.target_processes
        self._recovery_manager.max_retries = config.max_recovery_attempts
        self._recovery_manager.backoff_base = config.recovery_backoff_base
        self._recovery_manager.backoff_max = config.recovery_backoff_max
    
    def get_config(self) -> MultiModeCaptureConfig:
        """获取当前配置"""
        return self._config
    
    async def refresh_proxy_info(self) -> ProxyInfo:
        """刷新代理信息
        
        Returns:
            代理信息
        """
        self._proxy_info = await self._proxy_detector.detect()
        self._available_modes = await self._get_available_modes()
        return self._proxy_info
    
    def get_proxy_info(self) -> Optional[ProxyInfo]:
        """获取代理信息"""
        return self._proxy_info
    
    def get_wechat_processes(self) -> List[Dict[str, Any]]:
        """获取微信进程列表"""
        return [p.to_dict() for p in self._wechat_manager.get_processes()]
    
    def is_wechat_running(self) -> bool:
        """微信是否在运行"""
        return self._wechat_manager.is_wechat_running()
