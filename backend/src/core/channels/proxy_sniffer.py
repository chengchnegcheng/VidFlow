# -*- coding: utf-8 -*-
"""
代理嗅探器

使用 mitmproxy 实现 HTTP/HTTPS 代理，拦截并识别微信视频号视频 URL。
集成 VideoURLExtractor 进行统一的URL处理。

Validates: Requirements 6.2, 6.3
"""

import asyncio
import socket
import hashlib
import logging
import json
import gzip
import re
import sys
import time
import zlib
from html import unescape
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Tuple
from threading import Thread, Lock, RLock, Event
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from .models import (
    SnifferState,
    SnifferStatus,
    SnifferStartResult,
    DetectedVideo,
    EncryptionType,
    ErrorCode,
    get_error_message,
    VideoMetadata,
)
from .platform_detector import PlatformDetector
from .video_url_extractor import VideoURLExtractor, ExtractedVideo
from .http_monitor import HTTPMonitor, HTTPMonitorAddon
from .process_targets import (
    CHANNELS_BROWSER_HELPER_PROCESS_NAMES,
    LOCAL_CAPTURE_TARGET_PROCESSES,
    resolve_local_capture_processes,
    resolve_quic_target_processes,
)
from .quic_manager import QUICManager
from .ech_handler import ECHHandler
from ..downloaders.channels_downloader import ChannelsDownloader

try:
    import brotli  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    brotli = None


logger = logging.getLogger(__name__)
CHANNELS_INJECT_PROXY_PATH = "/__vidflow/channels/videos/inject"
CHANNELS_INJECT_SCRIPT_PATH = "/__vidflow/channels/inject.js"
CHANNELS_INJECT_HTML_HOSTS = [
    "channels.weixin.qq.com",
    "wxa.wxs.qq.com",
    "servicewechat.com",
    "liteapp.weixin.qq.com",
]
CHANNELS_INJECT_ASSET_HOSTS = CHANNELS_INJECT_HTML_HOSTS + ["res.wx.qq.com"]
CHANNELS_STATIC_PATH_SUFFIXES = (
    ".js", ".mjs", ".css", ".json", ".jpg", ".jpeg", ".png", ".webp",
    ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".map",
)

LOCAL_MODE_TARGET_PROCESSES = list(LOCAL_CAPTURE_TARGET_PROCESSES)
LOCAL_MODE_HELPER_PROCESSES = list(CHANNELS_BROWSER_HELPER_PROCESS_NAMES)
LOCAL_CAPTURE_ALLOW_HOST_PATTERNS = [
    r"(^|.*\.)qq\.com:\d+$",
    r"(^|.*\.)wechat\.com:\d+$",
    r"(^|.*\.)qpic\.cn:\d+$",
    r"(^|.*\.)qlogo\.cn:\d+$",
]
WECHAT_RENDERER_RECYCLE_PROCESSES = [
    "WeChatAppEx.exe",
    "WeChatApp.exe",
    "WeChatBrowser.exe",
    "WeChatPlayer.exe",
]
WECHAT_MAIN_PROCESS_NAMES = [
    "Weixin.exe",
    "WeChat.exe",
]
WECHAT_RENDERER_RECYCLE_COOLDOWN_SECONDS = 8.0
WECHAT_RENDERER_RECYCLE_MAX_ATTEMPTS = 3
WECHAT_RENDERER_ACTIVITY_TTL_SECONDS = 20.0
WECHAT_RENDERER_STARTUP_EVIDENCE_URL = "https://channels.weixin.qq.com/"
WECHAT_RENDERER_RECYCLE_HELPER_PROCESSES = list(CHANNELS_BROWSER_HELPER_PROCESS_NAMES)
CHANNELS_PAGE_PREFETCH_COOLDOWN_SECONDS = 12.0
CHANNELS_PAGE_PREFETCH_TIMEOUT_SECONDS = 10.0
CHANNELS_PAGE_PREFETCH_MAX_BYTES = 2 * 1024 * 1024


class ProxySniffer:
    """代理嗅探器

    使用 mitmproxy 实现 HTTP/HTTPS 代理，自动识别视频号视频 URL。
    集成 VideoURLExtractor 进行统一的URL处理和去重。

    Validates: Requirements 6.2, 6.3
    """

    def __init__(
        self,
        port: int = 8888,
        cert_dir: Optional[Path] = None,
        transparent_mode: bool = False,
        quic_blocking_enabled: bool = True,
        target_processes: Optional[List[str]] = None,
    ):
        """初始化代理嗅探器

        Args:
            port: 代理端口
            cert_dir: 证书目录
            transparent_mode: 是否使用透明代理模式（用于 WinDivert 透明捕获）
        """
        self.port = port
        self.cert_dir = cert_dir
        self.transparent_mode = transparent_mode
        self.quic_blocking_enabled = quic_blocking_enabled
        self.target_processes = resolve_local_capture_processes(target_processes)

        self._state = SnifferState.STOPPED
        self._detected_videos: List[DetectedVideo] = []
        self._video_urls: set = set()  # 用于去重（原始 URL）
        self._video_keys: set = set()  # 归一化后的去重键
        self._started_at: Optional[datetime] = None
        self._error_message: Optional[str] = None

        self._proxy_thread: Optional[Thread] = None
        self._master = None
        self._proxy_loop: Optional[asyncio.AbstractEventLoop] = None  # 代理线程的事件循环引用
        self._stop_requested = False
        # add_detected_video() may call update_video_metadata() on duplicate records.
        # Both paths need the same lock, so use an RLock to avoid self-deadlock.
        self._lock = RLock()

        # 视频检测回调
        self._on_video_detected: Optional[Callable[[DetectedVideo], None]] = None

        # 集成 VideoURLExtractor 进行统一URL处理
        self._video_url_extractor = VideoURLExtractor()

        # HTTP 监控器（用于提取 encfilekey）
        self._http_monitor: Optional[HTTPMonitor] = None
        self._video_sniffer_addon: Optional["VideoSnifferAddon"] = None
        self._quic_manager = QUICManager(
            target_processes=resolve_quic_target_processes(self.target_processes),
            on_packet_blocked=self._on_quic_packet_blocked,
        )

        # Runtime traffic counters for diagnostics.
        self._request_count: int = 0
        self._flow_count: int = 0
        self._mmtls_request_count: int = 0
        self._request_hosts: Dict[str, int] = {}
        self._last_request_at: Optional[datetime] = None
        self._recent_response_samples: List[Dict[str, Any]] = []
        self._channels_page_injection_kind: Optional[str] = None
        self._channels_page_injection_url: Optional[str] = None
        self._channels_page_injection_at: Optional[datetime] = None
        self._renderer_recycle_attempted: bool = False
        self._renderer_recycle_attempt_count: int = 0
        self._renderer_recycle_completed: bool = False
        self._renderer_recycle_reason: Optional[str] = None
        self._renderer_recycle_at: Optional[datetime] = None
        self._recent_renderer_process_activity: Dict[int, Tuple[str, float]] = {}

        # 端口-进程缓存（后台线程刷新，避免在 mitmproxy 回调中调用 psutil）
        self._port_process_cache: Dict[int, Tuple[Optional[str], Optional[int], float]] = {}
        self._port_process_cache_lock = Lock()
        self._port_cache_refresh_stop = Event()
        self._port_cache_refresh_thread: Optional[Thread] = None

    @property
    def is_running(self) -> bool:
        """代理是否正在运行"""
        return self._state == SnifferState.RUNNING

    def set_on_video_detected(self, callback: Callable[[DetectedVideo], None]) -> None:
        """设置视频检测回调

        Args:
            callback: 检测到视频时的回调函数
        """
        self._on_video_detected = callback

    def _handle_unexpected_proxy_exit(self) -> None:
        """Surface unexpected mitmproxy exits instead of leaving stale RUNNING state."""
        if self._stop_requested or self._state != SnifferState.RUNNING:
            return

        if self.transparent_mode:
            message = (
                "本地透明代理已意外退出：mitmproxy local redirect daemon 提前结束。"
                "请重新启动嗅探，并关闭会接管流量的 TUN/Fake-IP/系统代理后再试。"
            )
        else:
            message = "代理进程已意外退出，请重新启动嗅探。"

        self._state = SnifferState.ERROR
        self._error_message = message
        logger.error(message)

    def _on_quic_packet_blocked(self, src_port: int, dst_ip: str, dst_port: int) -> None:
        logger.debug("Blocked QUIC packet: %s -> %s:%s", src_port, dst_ip, dst_port)

    def set_target_processes(self, target_processes: List[str]) -> None:
        self.target_processes = resolve_local_capture_processes(target_processes)
        self._quic_manager.target_processes = resolve_quic_target_processes(self.target_processes)

    @staticmethod
    def _build_local_capture_allow_hosts() -> List[str]:
        """Restrict helper-browser local capture to WeChat/Tencent-related hosts."""
        return list(LOCAL_CAPTURE_ALLOW_HOST_PATTERNS)

    def get_quic_status(self) -> Dict[str, Any]:
        stats = self._quic_manager.get_stats().to_dict()
        return {
            "blocking_enabled": self.quic_blocking_enabled,
            "packets_blocked": stats.get("packets_blocked", 0),
            "packets_allowed": stats.get("packets_allowed", 0),
            "target_processes": list(self.target_processes),
            "quic_target_processes": resolve_quic_target_processes(self.target_processes),
        }

    async def toggle_quic_blocking(self, enabled: bool) -> Dict[str, Any]:
        self.quic_blocking_enabled = bool(enabled)
        if self.transparent_mode and self.is_running:
            if enabled:
                started = await self._quic_manager.start_blocking()
                if not started:
                    logger.warning("QUIC blocking failed to start while sniffer is running")
            else:
                await self._quic_manager.stop_blocking()
        return self.get_quic_status()

    async def start(self) -> SnifferStartResult:
        """启动代理服务器

        Returns:
            SnifferStartResult: 启动结果
        """
        if self._state == SnifferState.RUNNING:
            return SnifferStartResult(
                success=True,
                proxy_address=f"127.0.0.1:{self.port}"
            )

        if self._state in (SnifferState.STARTING, SnifferState.STOPPING):
            return SnifferStartResult(
                success=False,
                error_message="代理正在启动或停止中"
            )

        # 检查端口是否可用
        if not self._is_port_available(self.port):
            self._state = SnifferState.ERROR
            self._error_message = get_error_message(ErrorCode.PORT_IN_USE, port=self.port)
            return SnifferStartResult(
                success=False,
                error_message=self._error_message,
                error_code=ErrorCode.PORT_IN_USE
            )

        self._state = SnifferState.STARTING
        self._error_message = None
        self._stop_requested = False
        self._quic_manager.reset_stats()
        self._quic_manager.target_processes = resolve_quic_target_processes(self.target_processes)
        self.clear_videos()
        with self._lock:
            self._request_count = 0
            self._flow_count = 0
            self._mmtls_request_count = 0
            self._request_hosts.clear()
            self._last_request_at = None
            self._recent_response_samples.clear()
            self._channels_page_injection_kind = None
            self._channels_page_injection_url = None
            self._channels_page_injection_at = None
            self._renderer_recycle_attempted = False
            self._renderer_recycle_attempt_count = 0
            self._renderer_recycle_completed = False
            self._renderer_recycle_reason = None
            self._renderer_recycle_at = None
            self._recent_renderer_process_activity.clear()

        try:
            # 启动代理线程
            if self.transparent_mode and self.quic_blocking_enabled:
                quic_started = await self._quic_manager.start_blocking()
                if not quic_started:
                    logger.warning("QUIC blocking failed to start; video traffic may still bypass TCP capture")

            self._proxy_thread = Thread(target=self._run_proxy, daemon=True)
            self._proxy_thread.start()

            # 等待代理启动
            for _ in range(50):  # 最多等待 5 秒
                await asyncio.sleep(0.1)
                if self._state == SnifferState.RUNNING:
                    break
                if self._state == SnifferState.ERROR:
                    await self._quic_manager.stop_blocking()
                    return SnifferStartResult(
                        success=False,
                        error_message=self._error_message or "代理启动失败"
                    )

            if self._state != SnifferState.RUNNING:
                self._state = SnifferState.ERROR
                self._error_message = "代理启动超时"
                await self._quic_manager.stop_blocking()
                return SnifferStartResult(
                    success=False,
                    error_message=self._error_message
                )

            self._started_at = datetime.now()
            self._start_port_cache_refresh_thread()

            return SnifferStartResult(
                success=True,
                proxy_address=f"127.0.0.1:{self.port}"
            )

        except PermissionError:
            self._state = SnifferState.ERROR
            self._error_message = get_error_message(ErrorCode.PERMISSION_DENIED)
            await self._quic_manager.stop_blocking()
            return SnifferStartResult(
                success=False,
                error_message=self._error_message,
                error_code=ErrorCode.PERMISSION_DENIED
            )
        except Exception as e:
            self._state = SnifferState.ERROR
            self._error_message = f"启动失败: {str(e)}"
            logger.exception("Failed to start proxy")
            await self._quic_manager.stop_blocking()
            return SnifferStartResult(
                success=False,
                error_message=self._error_message
            )

    def _run_proxy(self) -> None:
        """在线程中运行代理"""
        loop = None
        try:
            # 在线程中创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._proxy_loop = loop  # 存储引用，供 stop() 跨线程调度 shutdown

            # 在事件循环中运行异步初始化和代理
            loop.run_until_complete(self._async_run_proxy())

        except Exception as e:
            if self._stop_requested and self._state in (SnifferState.STOPPING, SnifferState.STOPPED):
                logger.debug("Proxy loop exited during shutdown", exc_info=True)
            else:
                self._state = SnifferState.ERROR
                self._error_message = str(e)
                logger.exception("Proxy error")
        finally:
            self._proxy_loop = None
            # 清理事件循环中的所有待处理任务
            if loop and not loop.is_closed():
                try:
                    # 给 mitmproxy_rs Rust 层时间排空残余连接
                    loop.run_until_complete(asyncio.sleep(0.5))
                except Exception:
                    pass

                try:
                    # 关闭异步生成器和默认执行器
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass

                try:
                    # 取消所有待处理的任务
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()

                    # 等待所有任务完成取消
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as e:
                    logger.debug(f"Error cancelling pending tasks: {e}")

                try:
                    # 关闭事件循环
                    loop.close()
                except Exception as e:
                    logger.debug(f"Error closing event loop: {e}")

    async def _async_run_proxy(self) -> None:
        """异步运行代理"""
        from mitmproxy import options
        from mitmproxy.tools.dump import DumpMaster

        opts = options.Options(
            listen_host="127.0.0.1",
            listen_port=self.port,
            ssl_insecure=True,
        )

        # 如果启用透明模式（配合 WinDivert NAT 重定向）
        if self.transparent_mode:
            # 使用 mitmproxy 内置的 local 模式
            # 这个模式会自动使用 WinDivert 拦截指定进程的流量
            # 指定微信进程：WeChat.exe 和 WeChatAppEx.exe
            opts.mode = [f"local:{','.join(self.target_processes)}"]
            opts.allow_hosts = self._build_local_capture_allow_hosts()
            logger.info(
                "Starting mitmproxy in local mode (auto WinDivert) targeting processes: %s; allow_hosts=%s",
                ", ".join(self.target_processes),
                ", ".join(opts.allow_hosts),
            )
        else:
            # 显式代理模式：期望客户端配置代理并发送 CONNECT 请求
            logger.info(f"Starting mitmproxy in regular (explicit) mode on port {self.port}")

        # 如果有证书目录，设置证书路径
        if self.cert_dir:
            opts.confdir = str(self.cert_dir)

        # 恢复 mitmproxy 日志级别（上次 stop 时可能被设为 CRITICAL）
        try:
            import logging as _logging
            for _logger_name in ('mitmproxy', 'mitmproxy_rs', 'mitmproxy_rs.task'):
                _logging.getLogger(_logger_name).setLevel(_logging.WARNING)
        except Exception:
            pass

        self._master = DumpMaster(opts)

        # 创建 HTTP 监控器并设置回调
        self._http_monitor = HTTPMonitor(on_video_detected=self._on_http_video_detected)

        # 添加插件
        self._video_sniffer_addon = VideoSnifferAddon(self)
        self._master.addons.add(self._video_sniffer_addon)
        self._master.addons.add(HTTPMonitorAddon(self._http_monitor))

        self._state = SnifferState.RUNNING

        # 运行代理
        try:
            await self._master.run()
        finally:
            # master.run() 返回后（无论是正常 shutdown 还是异常退出），
            # 需要给 mitmproxy_rs Rust 层时间完成清理（关闭 WinDivert、释放端口等）。
            # 如果不等待，Rust 层仍会尝试在即将关闭的事件循环上创建任务，
            # 导致 "Event loop is closed" 错误持续到下次启动。
            try:
                # 确保 master 的 addon done() 钩子被调用（清理 LocalRedirector 等）
                if self._master:
                    self._master.shutdown()
                    # 让 mitmproxy_rs 处理完剩余的关闭回调
                    await asyncio.sleep(1.0)
            except Exception as e:
                logger.debug(f"Post-run cleanup error (expected during shutdown): {e}")

        self._handle_unexpected_proxy_exit()

    async def stop(self) -> bool:
        """停止代理服务器

        Returns:
            停止成功返回 True
        """
        if self._state == SnifferState.STOPPED:
            return True

        if self._state == SnifferState.STOPPING:
            return False

        self._stop_requested = True
        self._state = SnifferState.STOPPING

        try:
            self._stop_port_cache_refresh_thread()
            await self._quic_manager.stop_blocking()

            if self._master:
                # 关键修复：通过代理线程自己的事件循环调度 shutdown，
                # 确保 mitmproxy_rs Rust 层（WinDivert / LocalRedirector）
                # 能在正确的事件循环上执行清理回调。
                proxy_loop = self._proxy_loop
                if proxy_loop and not proxy_loop.is_closed():
                    try:
                        proxy_loop.call_soon_threadsafe(self._master.shutdown)
                    except RuntimeError:
                        # 事件循环可能已经关闭，回退到直接调用
                        self._master.shutdown()
                else:
                    self._master.shutdown()

                # 等待 master 完全停止
                for _ in range(30):  # 最多等待 3 秒
                    await asyncio.sleep(0.1)
                    if not hasattr(self._master, 'should_exit') or self._master.should_exit.is_set():
                        break

                self._master = None
                self._video_sniffer_addon = None

            # 在等待线程退出前，抑制 mitmproxy / mitmproxy_rs 的日志输出，
            # 避免 shutdown 期间 "Event loop is closed" 刷屏
            try:
                import logging as _logging
                for _logger_name in ('mitmproxy', 'mitmproxy_rs', 'mitmproxy_rs.task'):
                    _ml = _logging.getLogger(_logger_name)
                    _ml.setLevel(_logging.CRITICAL)
            except Exception:
                pass

            # 等待线程结束 — 线程内部会执行 mitmproxy_rs 排空和事件循环清理
            if self._proxy_thread and self._proxy_thread.is_alive():
                self._proxy_thread.join(timeout=15)

                # 如果线程还在运行，强制标记为停止
                if self._proxy_thread.is_alive():
                    logger.warning("Proxy thread did not stop gracefully")

            self._proxy_thread = None
            self._state = SnifferState.STOPPED
            self._started_at = None

            # 等待端口释放
            port_released = False
            for _ in range(50):  # 最多等待 5 秒
                if self._is_port_available(self.port):
                    port_released = True
                    break
                await asyncio.sleep(0.1)

            if not port_released:
                logger.warning("Port %s still in use after stop; next start may fallback to random port", self.port)

            logger.info("Proxy sniffer stopped successfully")
            return True

        except Exception as e:
            logger.exception("Failed to stop proxy")
            self._state = SnifferState.ERROR
            self._error_message = str(e)
            return False

    def get_status(self) -> SnifferStatus:
        """获取嗅探器状态

        Returns:
            SnifferStatus: 当前状态
        """
        return SnifferStatus(
            state=self._state,
            proxy_address=f"127.0.0.1:{self.port}" if self._state == SnifferState.RUNNING else None,
            proxy_port=self.port,
            videos_detected=len(self._detected_videos),
            started_at=self._started_at,
            error_message=self._error_message,
        )

    def get_detected_videos(self) -> List[DetectedVideo]:
        """获取检测到的视频列表

        Returns:
            检测到的视频列表
        """
        with self._lock:
            return list(self._detected_videos)

    def clear_videos(self) -> None:
        """清空检测到的视频列表"""
        with self._lock:
            self._detected_videos.clear()
            self._video_urls.clear()
            self._video_keys.clear()
            # 同时清除 VideoURLExtractor 的ID缓存
            self._video_url_extractor.clear_extracted_ids()

    def get_video_url_extractor(self) -> VideoURLExtractor:
        """获取视频URL提取器实例"""
        return self._video_url_extractor

    def record_request(self, url: str) -> None:
        """Record proxy request stats for diagnostics."""
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            host = ""

        is_mmtls = "/mmtls/" in (url or "").lower()

        with self._lock:
            self._request_count += 1
            self._last_request_at = datetime.now()
            if is_mmtls:
                self._mmtls_request_count += 1

            if host:
                self._request_hosts[host] = self._request_hosts.get(host, 0) + 1
                # Keep a bounded map to avoid unbounded growth.
                if len(self._request_hosts) > 50:
                    least_used_host = min(self._request_hosts, key=self._request_hosts.get)
                    self._request_hosts.pop(least_used_host, None)

    def record_response_flow(self) -> None:
        """Record processed response-flow count."""
        with self._lock:
            self._flow_count += 1

    def record_relevant_response(
        self,
        url: str,
        content_type: str,
        status_code: Optional[int],
        classification: str,
        detail: Optional[str] = None,
    ) -> None:
        """Record a bounded sample of relevant non-media responses for diagnostics."""
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            path = parsed.path or "/"
        except Exception:
            host = ""
            path = "/"

        if not host:
            return

        sample = {
            "host": host,
            "path": path[:120],
            "content_type": (content_type or "")[:120],
            "status_code": status_code,
            "classification": classification,
        }
        if detail:
            sample["detail"] = str(detail)[:180]

        with self._lock:
            self._recent_response_samples.append(sample)
            if len(self._recent_response_samples) > 20:
                self._recent_response_samples = self._recent_response_samples[-20:]

        if classification.startswith(("channels_html", "channels_js", "renderer_recycle")):
            logger.info(
                "[DIAG] %s: detail=%s type=%s url=%s",
                classification,
                detail or "-",
                (content_type or "<empty>")[:80],
                url[:120],
            )

    def note_channels_page_injection(self, kind: str, url: str) -> None:
        with self._lock:
            self._channels_page_injection_kind = str(kind or "").strip() or "unknown"
            self._channels_page_injection_url = str(url or "").strip() or None
            self._channels_page_injection_at = datetime.now()

    def note_renderer_process_activity(self, process_name: Optional[str], pid: Optional[int]) -> None:
        if not isinstance(pid, int) or pid <= 0:
            return

        normalized_name = str(process_name or "").strip()
        if not normalized_name:
            return

        allowed_names = {
            name.lower()
            for name in (
                WECHAT_RENDERER_RECYCLE_PROCESSES
                + WECHAT_RENDERER_RECYCLE_HELPER_PROCESSES
            )
        }
        if normalized_name.lower() not in allowed_names:
            return

        now = time.monotonic()
        with self._lock:
            self._recent_renderer_process_activity[pid] = (normalized_name, now)
            stale_pids = [
                cached_pid
                for cached_pid, (_, seen_at) in self._recent_renderer_process_activity.items()
                if now - seen_at > WECHAT_RENDERER_ACTIVITY_TTL_SECONDS
            ]
            for stale_pid in stale_pids:
                self._recent_renderer_process_activity.pop(stale_pid, None)

    def _get_recent_renderer_process_candidates(self) -> Dict[int, str]:
        now = time.monotonic()
        with self._lock:
            stale_pids = [
                pid
                for pid, (_, seen_at) in self._recent_renderer_process_activity.items()
                if now - seen_at > WECHAT_RENDERER_ACTIVITY_TTL_SECONDS
            ]
            for stale_pid in stale_pids:
                self._recent_renderer_process_activity.pop(stale_pid, None)
            return {
                pid: name
                for pid, (name, _) in self._recent_renderer_process_activity.items()
            }

    def has_channels_page_injection(self) -> bool:
        with self._lock:
            return self._channels_page_injection_at is not None

    def proactively_recycle_wechat_renderer_on_startup(self) -> bool:
        """Refresh existing WeChat browser renderers after proxy-mode startup.

        This helps when the Channels page was already open before VidFlow started,
        because those helper processes may never reload through the new proxy
        settings unless we explicitly recycle them once.
        """
        if not self.is_running or self.transparent_mode or self.has_channels_page_injection():
            return False

        matched_processes, _ = self._collect_wechat_renderer_processes(force_helpers=True)
        if not matched_processes:
            return False

        now = datetime.now()
        with self._lock:
            if (
                self._renderer_recycle_attempted
                and self._renderer_recycle_at is not None
                and (now - self._renderer_recycle_at).total_seconds()
                < WECHAT_RENDERER_RECYCLE_COOLDOWN_SECONDS
            ):
                return False
            if self._renderer_recycle_attempt_count >= WECHAT_RENDERER_RECYCLE_MAX_ATTEMPTS:
                self.record_relevant_response(
                    WECHAT_RENDERER_STARTUP_EVIDENCE_URL,
                    "",
                    None,
                    "renderer_recycle_skipped",
                    "startup_missing_channels_injection; explicit_proxy; max_attempts_reached",
                )
                return False

            self._renderer_recycle_attempted = True
            self._renderer_recycle_attempt_count += 1
            self._renderer_recycle_reason = "startup_missing_channels_injection"
            self._renderer_recycle_at = now

        recycled = self._recycle_wechat_renderer_processes(force_helpers=True)
        if recycled:
            with self._lock:
                self._renderer_recycle_completed = True
            logger.info(
                "Safely recycled WeChat renderer subprocesses after startup: %s",
                ", ".join(recycled),
            )
            self.record_relevant_response(
                WECHAT_RENDERER_STARTUP_EVIDENCE_URL,
                "",
                None,
                "renderer_recycle_completed",
                f"startup_missing_channels_injection; explicit_proxy; {', '.join(recycled)}",
            )
            return True

        self.record_relevant_response(
            WECHAT_RENDERER_STARTUP_EVIDENCE_URL,
            "",
            None,
            "renderer_recycle_deferred",
            "startup_missing_channels_injection; explicit_proxy; no_safe_renderer_candidates",
        )
        return False

    def maybe_recycle_wechat_renderer(
        self,
        reason: str,
        evidence_url: str = "",
        force_helpers: bool = False,
    ) -> bool:
        if not self.is_running:
            return False

        now = datetime.now()
        with self._lock:
            if self._channels_page_injection_at is not None:
                return False
            if (
                self._renderer_recycle_attempted
                and self._renderer_recycle_at is not None
                and (now - self._renderer_recycle_at).total_seconds()
                < WECHAT_RENDERER_RECYCLE_COOLDOWN_SECONDS
            ):
                return False
            if self._renderer_recycle_attempt_count >= WECHAT_RENDERER_RECYCLE_MAX_ATTEMPTS:
                mode_label = "transparent_mode" if self.transparent_mode else "explicit_proxy"
                self.record_relevant_response(
                    evidence_url or "https://channels.weixin.qq.com/",
                    "",
                    None,
                    "renderer_recycle_skipped",
                    f"{str(reason or '').strip() or 'unknown'}; {mode_label}; max_attempts_reached",
                )
                return False

            self._renderer_recycle_attempted = True
            self._renderer_recycle_attempt_count += 1
            self._renderer_recycle_reason = str(reason or "").strip() or "unknown"
            self._renderer_recycle_at = now

        mode_label = "transparent_mode" if self.transparent_mode else "explicit_proxy"
        disable_reason = "automatic_renderer_recycle_disabled"
        logger.warning(
            "Detected missed Channels page injection, but automatic WeChat renderer recycle is disabled: "
            "reason=%s mode=%s url=%s",
            self._renderer_recycle_reason,
            mode_label,
            (evidence_url or "https://channels.weixin.qq.com/")[:120],
        )
        self.record_relevant_response(
            evidence_url or WECHAT_RENDERER_STARTUP_EVIDENCE_URL,
            "",
            None,
            "renderer_recycle_deferred",
            f"{self._renderer_recycle_reason}; {mode_label}; {disable_reason}",
        )
        return False

    def _collect_wechat_renderer_processes(
        self,
        force_helpers: bool = False,
    ) -> Tuple[List[Any], Dict[int, str]]:
        try:
            import psutil
        except Exception:
            logger.warning("psutil is unavailable; cannot inspect WeChat renderer processes")
            return [], {}

        renderer_names = {name.lower() for name in WECHAT_RENDERER_RECYCLE_PROCESSES}
        helper_names = {name.lower() for name in WECHAT_RENDERER_RECYCLE_HELPER_PROCESSES}
        recent_candidates = self._get_recent_renderer_process_candidates()
        matched_processes = []
        labels_by_pid: Dict[int, str] = {}

        def get_cmdline(proc: Any) -> str:
            info = getattr(proc, "info", {}) or {}
            cmdline = info.get("cmdline")
            if isinstance(cmdline, str):
                return cmdline
            if isinstance(cmdline, (list, tuple)):
                return " ".join(str(part) for part in cmdline if part)
            try:
                dynamic_cmdline = proc.cmdline()
            except Exception:
                return ""
            if isinstance(dynamic_cmdline, str):
                return dynamic_cmdline
            if isinstance(dynamic_cmdline, (list, tuple)):
                return " ".join(str(part) for part in dynamic_cmdline if part)
            return ""

        def is_safe_helper_process(lowered_name: str, cmdline_lower: str) -> bool:
            if lowered_name == "msedgewebview2.exe":
                return any(
                    token in cmdline_lower
                    for token in (
                        "--webview-exe-name=weixin.exe",
                        "--webview-exe-name=wechat.exe",
                    )
                ) and "--type=renderer" in cmdline_lower
            if lowered_name == "qqbrowser.exe":
                return ("wechat" in cmdline_lower or "weixin" in cmdline_lower)
            return False

        def is_safe_renderer_process(lowered_name: str, cmdline_lower: str) -> bool:
            if lowered_name in helper_names:
                return is_safe_helper_process(lowered_name, cmdline_lower)
            if lowered_name in renderer_names:
                return "--type=renderer" in cmdline_lower
            return False

        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = (proc.info.get("name") or "").strip()
                    lowered_name = name.lower()
                    is_renderer = lowered_name in renderer_names
                    is_helper = lowered_name in helper_names
                    is_recent_helper = proc.pid in recent_candidates and is_helper
                    if not is_renderer and not is_helper:
                        continue
                    if is_helper and not (force_helpers or is_recent_helper):
                        continue
                    cmdline = get_cmdline(proc)
                    if not is_safe_renderer_process(lowered_name, cmdline.lower()):
                        continue
                    matched_processes.append(proc)
                    labels_by_pid[proc.pid] = f"{name}:{proc.pid}"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            logger.debug("Failed to enumerate WeChat renderer processes", exc_info=True)
            return [], {}

        return matched_processes, labels_by_pid

    def _recycle_wechat_renderer_processes(self, force_helpers: bool = False) -> List[str]:
        matched_processes, labels_by_pid = self._collect_wechat_renderer_processes(
            force_helpers=force_helpers
        )

        if not matched_processes:
            return []

        terminated_processes = []
        for proc in matched_processes:
            try:
                proc.terminate()
                terminated_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                logger.debug("Failed to terminate renderer process pid=%s", getattr(proc, "pid", None), exc_info=True)

        if not terminated_processes:
            return []

        try:
            _, alive = psutil.wait_procs(terminated_processes, timeout=2.0)
            if alive:
                logger.info(
                    "Some WeChat renderer processes are still alive after terminate signal: %s",
                    ", ".join(labels_by_pid.get(proc.pid, str(proc.pid)) for proc in alive),
                )
        except Exception:
            logger.debug("Failed waiting for renderer recycle completion", exc_info=True)

        with self._lock:
            for proc in terminated_processes:
                self._recent_renderer_process_activity.pop(proc.pid, None)

        return [labels_by_pid.get(proc.pid, str(proc.pid)) for proc in terminated_processes]

    def get_runtime_statistics(self) -> Dict[str, Any]:
        """Return runtime traffic statistics."""
        with self._lock:
            top_hosts = sorted(
                self._request_hosts.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:10]
            return {
                "request_count": self._request_count,
                "flow_count": self._flow_count,
                "mmtls_request_count": self._mmtls_request_count,
                "last_request_at": self._last_request_at.isoformat() if self._last_request_at else None,
                "top_hosts": top_hosts,
                "recent_response_samples": list(self._recent_response_samples),
                "channels_page_injection_kind": self._channels_page_injection_kind,
                "channels_page_injection_url": self._channels_page_injection_url,
                "channels_page_injection_at": (
                    self._channels_page_injection_at.isoformat()
                    if self._channels_page_injection_at
                    else None
                ),
                "renderer_recycle_attempted": self._renderer_recycle_attempted,
                "renderer_recycle_attempt_count": self._renderer_recycle_attempt_count,
                "renderer_recycle_completed": self._renderer_recycle_completed,
                "renderer_recycle_reason": self._renderer_recycle_reason,
                "renderer_recycle_at": (
                    self._renderer_recycle_at.isoformat()
                    if self._renderer_recycle_at
                    else None
                ),
            }

    def _on_http_video_detected(self, video_info: Dict[str, Any]) -> None:
        """HTTP 监控器检测到视频时的回调

        Args:
            video_info: 视频信息（包含 url 和 encfilekey）
        """
        try:
            url = video_info.get('url')
            encfilekey = video_info.get('encfilekey')

            if not url:
                return

            logger.info(f"HTTP 监控器检测到视频: {url[:100]}...")
            logger.info(f"  encfilekey: {encfilekey[:50] if encfilekey else 'None'}...")

            # 检查是否已经存在
            video_id = PlatformDetector.extract_video_id(url)
            if not video_id:
                video_id = hashlib.md5(url.encode()).hexdigest()[:16]
            query_params = parse_qs(urlparse(url).query)

            # 查找是否已存在（包含 taskid 跨画质去重）
            incoming_taskid = self._extract_taskid(url)
            existing_video = None
            with self._lock:
                for v in self._detected_videos:
                    if v.id == video_id or v.url == url:
                        existing_video = v
                        break
                    if incoming_taskid and self._extract_taskid(v.url) == incoming_taskid:
                        existing_video = v
                        break

            if existing_video:
                # encfilekey 只是资源标识，不是 decodeKey。
                # 这里不写入 decryption_key，避免后续误当作解密密钥。
                pass
            else:
                # 创建新视频
                from datetime import datetime
                video = DetectedVideo(
                    id=video_id,
                    url=url,
                    title=self._build_fallback_title(video_id, query_params),
                    thumbnail=None,
                    detected_at=datetime.now(),
                    encryption_type=self._infer_encryption_type(url),
                    decryption_key=None,
                )

                self.add_detected_video(video)
                logger.info(f"添加新视频: {video.title}")

        except Exception as e:
            logger.exception(f"处理 HTTP 监控器检测到的视频失败: {e}")

    def is_video_url(self, url: str) -> bool:
        """检查URL是否是视频号相关的视频URL

        使用 VideoURLExtractor 进行统一检查。

        Args:
            url: URL字符串

        Returns:
            是否是视频URL
        """
        return self._video_url_extractor.is_video_url(url)

    @staticmethod
    def _normalize_decode_key(value: Optional[str]) -> Optional[str]:
        """Normalize numeric uint64 decodeKey values from strings or Long-like objects."""
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return str(value) if value > 0 else None
        if isinstance(value, float):
            if value > 0 and value.is_integer():
                return str(int(value))
            return None
        if isinstance(value, (list, tuple, set)):
            for item in value:
                normalized_item = ProxySniffer._normalize_decode_key(item)
                if normalized_item:
                    return normalized_item
            return None
        if isinstance(value, dict):
            for key in (
                "decodeKey",
                "decode_key",
                "decodeKey64",
                "decode_key64",
                "decryptKey",
                "decrypt_key",
                "decryptionKey",
                "decryption_key",
                "decryptSeed",
                "decrypt_seed",
                "seed",
                "seedValue",
                "seed_value",
                "mediaKey",
                "media_key",
                "videoKey",
                "video_key",
                "dk",
                "$numberLong",
                "value",
            ):
                if key in value:
                    normalized_nested = ProxySniffer._normalize_decode_key(value.get(key))
                    if normalized_nested:
                        return normalized_nested
            low = value.get("low")
            high = value.get("high")
            if isinstance(low, int) and isinstance(high, int):
                combined = ((high & 0xFFFFFFFF) << 32) | (low & 0xFFFFFFFF)
                return str(combined) if combined > 0 else None

        candidate = str(value).strip()
        matched = re.fullmatch(r"([1-9]\d{0,127})(?:n|\.0)?", candidate)
        return matched.group(1) if matched else None

    @staticmethod
    def _sanitize_video_title(value: Optional[str]) -> Optional[str]:
        """Drop generic placeholder titles so callers can rebuild a stable one."""
        if value is None:
            return None
        title = str(value).strip()
        if not title:
            return None

        normalized = re.sub(r"\s+", " ", title)
        if normalized in {"\u89c6\u9891\u53f7", "\u5fae\u4fe1\u89c6\u9891\u53f7"}:
            return None
        if re.fullmatch(r"微信视频号\s+\d{2}:\d{2}:\d{2}", normalized):
            return None
        if re.fullmatch(r"视频号视频\s+[A-Za-z0-9]{8,32}", normalized):
            return None
        if re.fullmatch(r"channels_[A-Za-z0-9_-]{6,}", normalized, re.IGNORECASE):
            return None

        lowered = normalized.lower()
        if lowered in {"_", "-", "null", "undefined", "browser", "ui", "ie=edge"}:
            return None
        if re.fullmatch(
            r"(?:video\s+player(?:\s+is)?\s+loading|loading(?:\s+video(?:\s+player)?)?|video\s+loading)\.?",
            lowered,
            re.IGNORECASE,
        ):
            return None
        if lowered.endswith((".css", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico")):
            return None
        if lowered.endswith(".js") and ("index" in lowered or "publish" in lowered or "main" in lowered):
            return None
        if normalized.isascii() and " " not in normalized and re.fullmatch(r"^[a-zA-Z_$][\w$]*\(.*\)$", normalized):
            return None
        if len(normalized) <= 1 and normalized.isascii() and not normalized.isalnum():
            return None
        if any(
            marker in lowered
            for marker in (
                "<%",
                "%>",
                "document.",
                "window.",
                "queryselector",
                "getelementsby",
                "__append",
                "function(",
                "function ",
                "=>",
                "null==",
                "void 0",
                "feedback_debug_url",
                "avatarimg",
                "head_img",
                "style.",
                ":after",
                "content:",
            )
        ):
            return None
        if ProxySniffer._looks_like_expression_title(normalized):
            return None
        if any(token in normalized for token in ("{", "}", ";")):
            return None

        # 过滤对话框/无障碍/accessibility 噪声文本
        if re.match(r"^(?:Beginning|End) of (?:dialog|modal)", normalized, re.IGNORECASE):
            return None
        if re.search(r"Escape will (?:cancel|close)", normalized, re.IGNORECASE):
            return None
        # "Close Modal Dialog" 等 UI 元素组合标题
        _ui_words = {
            "dialog", "modal", "overlay", "popup", "tooltip", "menu",
            "loading", "close", "open", "cancel", "confirm", "submit",
            "ok", "yes", "no", "back", "next", "previous", "retry",
            "share", "copy", "download", "delete", "edit", "save", "reset",
            "search", "button", "icon", "header", "footer", "sidebar",
            "navigation", "content", "wrapper", "container", "panel",
            "video", "player", "audio", "media", "controls", "progress",
            "seekbar", "volume", "fullscreen", "play", "pause", "mute",
            "unmute", "settings", "subtitles", "captions", "quality",
        }
        title_words = set(normalized.lower().replace(".", "").split())
        if title_words and title_words.issubset(_ui_words):
            return None
        if re.fullmatch(
            r"(?:please wait|sign in|log in|log out|sign up)\s*\.?",
            normalized,
            re.IGNORECASE,
        ):
            return None
        if re.fullmatch(
            r"(?:播放|暂停|停止|上一个|下一个|静音|取消静音|音量|分享|转发|收藏|点赞|评论|关注|已关注)\s*",
            normalized,
        ):
            return None
        # 过滤设置/配置界面的英文 UI 指令文本
        if re.search(r"(?:restore|reset|revert)\s+(?:all\s+)?(?:settings|preferences|options|defaults)", normalized, re.IGNORECASE):
            return None
        if re.search(r"(?:default|original)\s+(?:settings|values|configuration)", normalized, re.IGNORECASE):
            return None
        if re.match(r"^(?:are you sure|do you want|would you like|this (?:action|operation|will))\b", normalized, re.IGNORECASE):
            return None
        if re.match(r"^(?:click|tap|press|drag|swipe|scroll|select|choose|pick|enter|type)\s+(?:here|to|the|a|an)\b", normalized, re.IGNORECASE):
            return None
        if re.match(r"^(?:powered by|copyright|all rights reserved|terms of|privacy policy|cookie)\b", normalized, re.IGNORECASE):
            return None
        # 过滤纯英文且像 UI 指令的长句
        if normalized.isascii() and len(normalized) > 10 and re.search(
            r"\b(?:to (?:the|your|this|all|its)|settings|preferences|options|default|restore|reset|enable|disable|allow|deny|accept|reject|dismiss)\b",
            normalized,
            re.IGNORECASE,
        ):
            return None

        # 过滤纯 ASCII 无空格的 CamelCase 拼接词（常见于 CSS 属性值被误提取为标题）
        # 例如 "TransparencyOpaqueSemi-TransparentTransparent"
        if normalized.isascii() and " " not in normalized and len(normalized) > 15:
            camel_parts = re.findall(r"[A-Z][a-z]+", normalized)
            if len(camel_parts) >= 3:
                css_like_words = {
                    "transparent", "opaque", "transparency", "semi",
                    "visible", "hidden", "inherit", "initial", "none",
                    "auto", "normal", "bold", "italic", "block", "inline",
                    "absolute", "relative", "fixed", "static", "sticky",
                }
                matches = sum(1 for p in camel_parts if p.lower() in css_like_words)
                if matches >= 2:
                    return None

        return title

    @staticmethod
    def _looks_like_expression_title(value: Optional[str]) -> bool:
        if value is None:
            return False

        candidate = re.sub(r"\s+", " ", str(value).strip())
        if not candidate:
            return False

        lowered = candidate.lower()
        compact_ascii = candidate.isascii() and " " not in candidate
        if re.fullmatch(r"(?:document|window|globalThis|self)\.[A-Za-z_$][\w$]*", candidate):
            return True
        if compact_ascii and re.fullmatch(r"\.?(?:concat|join|map|filter|slice)\([^)]*\)", lowered):
            return True
        if compact_ascii and any(
            marker in lowered
            for marker in (
                ".objectnonceid",
                ".value",
                ".content",
                ".description",
                ".title",
                ".desc",
                ".nickname",
            )
        ):
            return True
        if compact_ascii and any(
            marker in lowered
            for marker in (
                "document.",
                "window.",
                "queryselector",
                "getelementsby",
                "function(",
                "function ",
                "return ",
                "=>",
            )
        ):
            return True
        if compact_ascii and "." in candidate and re.search(r"[()[\]=]", candidate):
            return True
        return False

    @classmethod
    def _score_video_title(cls, value: Optional[str]) -> int:
        normalized = cls._sanitize_video_title(value)
        if not normalized:
            return 0

        compact = re.sub(r"\s+", " ", normalized).strip()
        score = 10
        if re.search(r"\s", compact):
            score += 2
        if 4 <= len(compact) <= 80:
            score += 2
        score += min(len(compact), 48) // 12
        return score

    @classmethod
    def _pick_better_title(cls, current: Optional[str], incoming: Optional[str]) -> Optional[str]:
        normalized_current = cls._sanitize_video_title(current)
        normalized_incoming = cls._sanitize_video_title(incoming)

        if not normalized_current:
            return normalized_incoming
        if not normalized_incoming:
            return normalized_current

        current_score = cls._score_video_title(normalized_current)
        incoming_score = cls._score_video_title(normalized_incoming)
        if incoming_score > current_score:
            return normalized_incoming
        if incoming_score == current_score and len(normalized_incoming) > len(normalized_current) + 4:
            return normalized_incoming
        return normalized_current


    @staticmethod
    def _looks_like_placeholder_nonce(value: Optional[str]) -> bool:
        if value is None:
            return False

        candidate = re.sub(r"\s+", " ", str(value).strip())
        if not candidate:
            return False
        if re.fullmatch(r"pc-\d{8,}", candidate, re.IGNORECASE):
            return True
        if re.fullmatch(r"[0-9a-f]{16,64}", candidate, re.IGNORECASE):
            return True
        if (
            re.fullmatch(r"[A-Za-z0-9_-]{8,32}", candidate)
            and any(ch.isdigit() for ch in candidate)
            and not re.search(r"[\u4e00-\u9fff\s]", candidate)
        ):
            return True
        return False

    @staticmethod
    def _extract_thumbnail_url(value: Any) -> Optional[str]:
        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, (list, tuple, set)):
            for item in value:
                candidate = ProxySniffer._extract_thumbnail_url(item)
                if candidate:
                    return candidate
            return None

        if isinstance(value, dict):
            for key in (
                'url', 'src', 'thumbUrl', 'thumb_url', 'cover', 'coverUrl', 'cover_url',
                'coverImage', 'cover_image', 'coverImg', 'cover_img', 'coverImgUrl',
                'cover_img_url', 'poster', 'posterUrl', 'poster_url', 'imageUrl',
                'image_url', 'headUrl', 'head_url', 'thumb', 'thumburl', 'value',
            ):
                if key in value:
                    candidate = ProxySniffer._extract_thumbnail_url(value.get(key))
                    if candidate:
                        return candidate
            for nested_value in value.values():
                candidate = ProxySniffer._extract_thumbnail_url(nested_value)
                if candidate:
                    return candidate
            return None

        candidate = unescape(
            str(value).replace("\\u0026", "&").replace("\\/", "/")
        ).strip().strip('"\'')
        if not candidate:
            return None
        if candidate.startswith('//'):
            return f"https:{candidate}"
        if candidate.startswith(('http://', 'https://')):
            return candidate
        if re.match(
            r'^(?:res\.wx\.qq\.com|[^/]*(?:qpic|wx\.qlogo|wx\.qpic|qlogo)\.[^/]+)/',
            candidate,
            re.IGNORECASE,
        ):
            return f"https://{candidate.lstrip('/')}"
        return None
    @staticmethod
    def _is_plausible_metadata_cache_key(value: Optional[str]) -> bool:
        if value is None:
            return False

        candidate = str(value).strip()
        if not candidate or len(candidate) < 6 or len(candidate) > 256:
            return False

        lowered = candidate.lower()
        if lowered in {"null", "undefined", "none", "true", "false", "browser"}:
            return False
        if re.search(r"\s", candidate):
            return False
        if any(
            marker in lowered
            for marker in (
                "<%",
                "%>",
                "document.",
                "window.",
                "queryselector",
                "getelementsby",
                "__append",
                "function(",
                "function ",
                "=>",
                "null==",
                "void 0",
                "avatarimg",
                "head_img",
                "feedback_debug_url",
            )
        ):
            return False
        if any(ch in candidate for ch in '<>"\'`{}()[];,\\|'):
            return False
        if candidate.startswith(("http://", "https://", "//", "/")):
            return False

        return bool(re.fullmatch(r"[A-Za-z0-9_.:%=-]{6,256}", candidate))

    @staticmethod
    def _infer_encryption_type(url: Optional[str], decode_key: Optional[str] = None) -> EncryptionType:
        """Infer WeChat Channels encryption from URL characteristics."""
        normalized_decode_key = ProxySniffer._normalize_decode_key(decode_key)
        if normalized_decode_key:
            return EncryptionType.ISAAC64

        if not url:
            return EncryptionType.UNKNOWN

        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            path_lower = (parsed.path or "").lower()
            if "encfilekey" in query_params or "stodownload" in path_lower:
                return EncryptionType.ISAAC64
        except Exception:
            logger.debug("Failed to infer channels encryption type", exc_info=True)

        return EncryptionType.UNKNOWN

    @staticmethod
    def _build_fallback_title(
        video_id: Optional[str],
        query_params: Optional[Dict[str, List[str]]] = None,
    ) -> str:
        """Build a stable placeholder title when real metadata is unavailable."""
        query_params = query_params or {}

        candidate: Optional[str] = None
        for key in ("feedid", "feedId", "objectid", "objectId", "taskid", "taskId"):
            value = query_params.get(key, [None])[0]
            if not value:
                continue
            candidate = str(value).split("-")[-1][:12]
            if candidate:
                break

        if not candidate and video_id:
            candidate = str(video_id)[:12]

        if not candidate:
            candidate = datetime.now().strftime("%H%M%S")

        return f"channels_{candidate}"

    @staticmethod
    def _normalize_metadata_cache_keys(values: Any) -> List[str]:
        """Normalize metadata cache keys supplied by injected page scans."""
        normalized: List[str] = []

        def visit(value: Any) -> None:
            if value is None:
                return
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    visit(item)
                return

            text = str(value).strip()
            if not text or text in normalized:
                return
            if not ProxySniffer._is_plausible_metadata_cache_key(text):
                return

            normalized.append(text)

        visit(values)
        return normalized

    def _merge_cached_metadata(self, cache_keys: Optional[List[str]]) -> Optional[VideoMetadata]:
        """Merge late-arriving cached metadata for one or more channels cache keys."""
        normalized_keys = self._normalize_metadata_cache_keys(cache_keys)
        if not normalized_keys or not self._video_sniffer_addon:
            return None

        merged = VideoMetadata()
        with self._video_sniffer_addon._metadata_cache_lock:
            for cache_key in normalized_keys:
                metadata = self._video_sniffer_addon._metadata_cache.get(cache_key)
                if not metadata:
                    continue
                preferred_title = self._pick_better_title(merged.title, metadata.title)
                if preferred_title:
                    merged.title = preferred_title
                if metadata.duration is not None:
                    merged.duration = metadata.duration
                if metadata.resolution:
                    merged.resolution = metadata.resolution
                if metadata.filesize is not None:
                    merged.filesize = metadata.filesize
                if metadata.thumbnail:
                    merged.thumbnail = metadata.thumbnail
                if metadata.width is not None:
                    merged.width = metadata.width
                if metadata.height is not None:
                    merged.height = metadata.height
                if metadata.decode_key:
                    merged.decode_key = metadata.decode_key

        merged.title = self._sanitize_video_title(merged.title)
        merged.thumbnail = self._extract_thumbnail_url(merged.thumbnail)
        merged.decode_key = self._normalize_decode_key(merged.decode_key)
        if not merged.resolution and merged.width and merged.height:
            merged.resolution = f"{merged.width}x{merged.height}"

        if not any(
            [
                merged.title,
                merged.duration,
                merged.resolution,
                merged.filesize,
                merged.thumbnail,
                merged.decode_key,
            ]
        ):
            return None

        return merged

    def reconcile_cached_metadata(self, cache_keys: Optional[List[str]]) -> int:
        """Apply late-arriving cached metadata back onto already detected videos."""
        normalized_keys = self._normalize_metadata_cache_keys(cache_keys)
        merged = self._merge_cached_metadata(normalized_keys)
        if not merged:
            return 0

        key_set = set(normalized_keys)
        updated = 0
        for video in self.get_detected_videos():
            video_cache_keys = set(self._build_metadata_cache_keys(video.url))
            if not video_cache_keys.intersection(key_set):
                continue
            if self.update_video_metadata(
                video_id=video.id,
                url=video.url,
                title=merged.title,
                duration=merged.duration,
                resolution=merged.resolution,
                filesize=merged.filesize,
                thumbnail=merged.thumbnail,
                # 不从缓存借用 decodeKey：每个画质/URL 有独立加密密钥
            ):
                updated += 1

        if updated:
            logger.info(
                "Reconciled cached channels metadata into %s detected video(s) using %s cache key(s)",
                updated,
                len(normalized_keys),
            )
        return updated

    def add_detected_video(self, video: DetectedVideo) -> bool:
        """添加检测到的视频

        Args:
            video: 检测到的视频

        Returns:
            如果是新视频返回 True，如果是重复的返回 False
        """
        with self._lock:
            normalized_url = video.url.strip()
            key = PlatformDetector.extract_video_id(video.url)
            if not key:
                key = hashlib.md5(normalized_url.encode()).hexdigest()

            # 提取 taskid 用于跨画质去重（同一视频不同 idx 共享 taskid）
            incoming_taskid = self._extract_taskid(normalized_url)

            for existing in self._detected_videos:
                existing_url = existing.url.strip()
                # 基础去重：id 或 URL 完全匹配
                id_match = existing.id == video.id
                url_match = existing_url == normalized_url
                # 扩展去重：同 taskid 的不同画质
                taskid_match = False
                if incoming_taskid and not id_match and not url_match:
                    existing_taskid = self._extract_taskid(existing_url)
                    taskid_match = existing_taskid == incoming_taskid
                if id_match or url_match or taskid_match:
                    # 当新 URL 有 taskid 而旧 URL 没有时，升级为带认证参数的完整 URL
                    # 带 taskid/sign/basedata 的 URL 是经过认证的下载链接，能正常下载
                    existing_taskid = self._extract_taskid(existing_url)
                    if incoming_taskid and not existing_taskid:
                        existing.url = normalized_url
                    # 更新已有的视频信息
                    self.update_video_metadata(
                        video_id=existing.id,
                        url=existing.url,
                        title=video.title,
                        duration=video.duration,
                        resolution=video.resolution,
                        filesize=video.filesize,
                        thumbnail=video.thumbnail,
                        encryption_type=video.encryption_type,
                        decryption_key=video.decryption_key,
                    )
                    return False
            for existing in self._detected_videos:
                if not self._should_merge_related_detected_video(existing, video):
                    continue

                preferred_title = self._pick_better_title(existing.title, video.title)
                if preferred_title:
                    existing.title = preferred_title
                if video.duration is not None:
                    existing.duration = video.duration
                if video.resolution:
                    existing.resolution = video.resolution
                if video.filesize is not None:
                    existing.filesize = video.filesize
                if video.thumbnail:
                    existing.thumbnail = video.thumbnail
                if video.encryption_type is not None and getattr(video.encryption_type, "value", video.encryption_type) != "unknown":
                    existing.encryption_type = video.encryption_type
                if video.decryption_key:
                    existing.decryption_key = video.decryption_key
                if isinstance(video.detected_at, datetime) and video.detected_at > existing.detected_at:
                    existing.detected_at = video.detected_at
                if video.decryption_key and normalized_url and existing.url.strip() != normalized_url:
                    existing.url = normalized_url
                self._video_urls.add(normalized_url)
                self._video_keys.add(key)
                return False
            if normalized_url in self._video_urls or key in self._video_keys:
                return False

            self._video_urls.add(normalized_url)
            self._video_keys.add(key)
            self._detected_videos.append(video)

            # 触发回调
            if self._on_video_detected:
                try:
                    self._on_video_detected(video)
                except Exception:
                    logger.exception("Error in video detected callback")

            return True

    @staticmethod
    def _extract_taskid(url: str) -> Optional[str]:
        """从 URL 中提取 taskid 参数（同一视频不同画质共享 taskid）。"""
        try:
            query_params = parse_qs(urlparse(url).query)
            for param in ('taskid', 'taskId'):
                values = query_params.get(param)
                if values and values[0]:
                    return values[0].strip()
        except Exception:
            pass
        return None

    @classmethod
    def _should_merge_related_detected_video(cls, current: DetectedVideo, incoming: DetectedVideo) -> bool:
        """Heuristically collapse rotating channels URLs for the same visible video."""
        current_title = cls._sanitize_video_title(current.title)
        incoming_title = cls._sanitize_video_title(incoming.title)
        if not current_title or not incoming_title or current_title != incoming_title:
            return False

        current_thumb = cls._extract_thumbnail_url(current.thumbnail)
        incoming_thumb = cls._extract_thumbnail_url(incoming.thumbnail)
        if current_thumb and incoming_thumb and current_thumb != incoming_thumb:
            return False
        if not current_thumb and not incoming_thumb:
            return False

        if (
            current.duration is not None
            and incoming.duration is not None
            and abs(int(current.duration) - int(incoming.duration)) > 1
        ):
            return False
        if current.resolution and incoming.resolution and current.resolution != incoming.resolution:
            return False

        current_key = cls._normalize_decode_key(current.decryption_key)
        incoming_key = cls._normalize_decode_key(incoming.decryption_key)
        if current_key and incoming_key:
            return current_key == incoming_key
        if current_key or incoming_key:
            # 一方有 key 一方没有：同标题 + 已通过缩略图检查 → 同一视频的不同检测路径
            return True

        current_type = str(getattr(current.encryption_type, "value", current.encryption_type) or "")
        incoming_type = str(getattr(incoming.encryption_type, "value", incoming.encryption_type) or "")
        if "isaac64" not in {current_type.lower(), incoming_type.lower()}:
            return False

        return bool(current.duration is not None or incoming.duration is not None)

    def update_video_metadata(
        self,
        *,
        video_id: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        duration: Optional[int] = None,
        resolution: Optional[str] = None,
        filesize: Optional[int] = None,
        thumbnail: Optional[str] = None,
        encryption_type: Optional[EncryptionType] = None,
        decryption_key: Optional[str] = None,
    ) -> bool:
        """更新已记录的视频信息"""
        if not video_id and not url:
            return False

        with self._lock:
            target: Optional[DetectedVideo] = None
            for existing in self._detected_videos:
                if (video_id and existing.id == video_id) or (url and existing.url == url):
                    target = existing
                    break

            if not target:
                return False

            updated = False
            preferred_title = self._pick_better_title(target.title, title)
            if preferred_title and preferred_title != target.title:
                target.title = preferred_title
                updated = True

            mapping = {
                "duration": duration,
                "resolution": resolution,
                "filesize": filesize,
                "thumbnail": thumbnail,
                "encryption_type": encryption_type,
                "decryption_key": decryption_key,
            }

            for field, value in mapping.items():
                if value is None:
                    continue
                if getattr(target, field) != value:
                    setattr(target, field, value)
                    updated = True

            return updated

    @staticmethod
    def _build_metadata_cache_keys(url: Optional[str]) -> List[str]:
        """Build metadata cache keys from a channels resource URL."""
        if not url:
            return []

        normalized_url = PlatformDetector.normalize_channels_video_url(url)
        parsed = urlparse(normalized_url)
        query_params = parse_qs(parsed.query)
        cache_keys: List[str] = []

        video_id = PlatformDetector.extract_video_id(normalized_url)
        if video_id:
            cache_keys.append(video_id)

        for key_param in [
            "encfilekey", "m", "taskid", "taskId",
            "objectid", "feedid", "objectId", "feedId",
            "filekey", "videoId", "video_id", "mediaId", "mediaid",
        ]:
            value = query_params.get(key_param, [None])[0]
            if value and value not in cache_keys:
                cache_keys.append(value)

        # 对长 encfilekey 类型的值添加截断前缀版本，用于跨清晰度模糊匹配
        # 同一视频不同 spec 共享 encfilekey 前缀（约 36 字符）
        for key in list(cache_keys):
            if len(key) > 40:
                prefix_key = f"pfx:{key[:36]}"
                if prefix_key not in cache_keys:
                    cache_keys.append(prefix_key)

        return cache_keys

    def ingest_injected_video(
        self,
        *,
        url: Optional[str],
        title: Optional[str] = None,
        thumbnail: Optional[str] = None,
        duration: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        filesize: Optional[int] = None,
        decode_key: Optional[str] = None,
        page_url: Optional[str] = None,
        extra_cache_keys: Optional[List[str]] = None,
    ) -> Optional[DetectedVideo]:
        """Merge JS-injected metadata into detected video records and caches."""
        normalized_url = PlatformDetector.normalize_channels_video_url((url or "").strip())
        if not normalized_url:
            return None

        # 过滤缩略图 URL：/20304/ 和 /20350/ 是图片路径，picformat 参数表示缩略图
        url_lower = normalized_url.lower()
        if "/20304/stodownload" in url_lower or "/20350/stodownload" in url_lower:
            logger.debug("ingest_injected_video: 跳过缩略图路径 URL: %s", normalized_url[:120])
            return None
        if "picformat=" in url_lower or "wxampicformat=" in url_lower:
            logger.debug("ingest_injected_video: 跳过含 picformat 参数的 URL: %s", normalized_url[:120])
            return None

        video_id = PlatformDetector.extract_video_id(normalized_url)
        if not video_id:
            video_id = hashlib.md5(normalized_url.encode()).hexdigest()[:16]

        normalized_title = self._sanitize_video_title(title)
        normalized_thumbnail = self._extract_thumbnail_url(thumbnail)
        normalized_decode_key = self._normalize_decode_key(decode_key)

        resolution = None
        if width and height and int(width) > 0 and int(height) > 0:
            resolution = f"{int(width)}x{int(height)}"

        metadata = VideoMetadata(
            title=normalized_title,
            duration=int(duration) if duration else None,
            resolution=resolution,
            filesize=int(filesize) if filesize else None,
            thumbnail=normalized_thumbnail,
            width=int(width) if width else None,
            height=int(height) if height else None,
            decode_key=normalized_decode_key,
        )

        cache_keys = self._build_metadata_cache_keys(normalized_url)
        for extra_url in [page_url]:
            for cache_key in self._build_metadata_cache_keys(extra_url):
                if cache_key not in cache_keys:
                    cache_keys.append(cache_key)
        for cache_key in self._normalize_metadata_cache_keys(extra_cache_keys):
            if cache_key not in cache_keys:
                cache_keys.append(cache_key)

        if self._video_sniffer_addon:
            self._video_sniffer_addon.cache_external_metadata(metadata, cache_keys)
            self.reconcile_cached_metadata(cache_keys)

        merged_metadata = self._merge_cached_metadata(cache_keys)
        preferred_title = self._pick_better_title(
            normalized_title,
            merged_metadata.title if merged_metadata else None,
        )
        preferred_duration = metadata.duration
        if preferred_duration is None and merged_metadata:
            preferred_duration = merged_metadata.duration

        preferred_resolution = metadata.resolution or (merged_metadata.resolution if merged_metadata else None)
        preferred_filesize = metadata.filesize
        if preferred_filesize is None and merged_metadata:
            preferred_filesize = merged_metadata.filesize

        preferred_thumbnail = normalized_thumbnail or (merged_metadata.thumbnail if merged_metadata else None)
        # decodeKey 不能从缓存借用：每个画质/URL 有独立的加密密钥，
        # 缓存中的 key 可能属于另一个画质的 URL，借用会导致解密失败。
        preferred_decode_key = normalized_decode_key

        fallback_query = parse_qs(urlparse(normalized_url).query)
        fallback_title = self._build_fallback_title(video_id, fallback_query)

        updated = self.update_video_metadata(
            video_id=video_id,
            url=normalized_url,
            title=preferred_title,
            duration=preferred_duration,
            resolution=preferred_resolution,
            filesize=preferred_filesize,
            thumbnail=preferred_thumbnail,
            decryption_key=preferred_decode_key,
        )

        if not updated:
            video = DetectedVideo(
                id=video_id,
                url=normalized_url,
                title=preferred_title or fallback_title,
                duration=preferred_duration,
                resolution=preferred_resolution,
                filesize=preferred_filesize,
                thumbnail=preferred_thumbnail,
                detected_at=datetime.now(),
                encryption_type=self._infer_encryption_type(normalized_url, preferred_decode_key),
                decryption_key=preferred_decode_key,
            )
            self.add_detected_video(video)

        with self._lock:
            for existing in self._detected_videos:
                if existing.id == video_id or existing.url.strip() == normalized_url:
                    return existing

        return None

    def add_video_from_url(self, url: str, title: Optional[str] = None) -> Optional[DetectedVideo]:
        """从 URL 手动添加视频

        Args:
            url: 视频 URL
            title: 可选的视频标题

        Returns:
            添加成功返回视频对象，失败返回 None
        """
        # Normalize fake-IP style URLs so downstream detection/downloader can handle them.
        url = PlatformDetector.normalize_channels_video_url(url)

        # 验证 URL
        if not url or not url.startswith(('http://', 'https://')):
            logger.warning(f"Invalid URL: {url}")
            return None

        # 提取视频 ID
        video_id = PlatformDetector.extract_video_id(url)
        if not video_id:
            video_id = hashlib.md5(url.encode()).hexdigest()[:16]

        cached_metadata = self._merge_cached_metadata(self._build_metadata_cache_keys(url))

        # 提取解密密钥（仅保留数字 decodeKey）
        # 优先从 URL 自身参数提取，其次使用精确缓存匹配的 key
        decryption_key = self._normalize_decode_key(
            PlatformDetector.extract_decryption_key(url)
        )
        if not decryption_key and cached_metadata and cached_metadata.decode_key:
            decryption_key = self._normalize_decode_key(cached_metadata.decode_key)

        # 先清洗外部传入标题，再尝试复用缓存的页面元数据
        title = self._sanitize_video_title(title) or (cached_metadata.title if cached_metadata else None)

        # 自动生成标题（确保标题永远不为 None）
        if not title:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            title = self._build_fallback_title(video_id, query_params)

        # 二次清洗自动生成标题，避免落入“视频号视频 Cvvj5Ix3”这类噪声
        title = self._sanitize_video_title(title)
        if not title:
            title = self._build_fallback_title(video_id)

        thumbnail = cached_metadata.thumbnail if cached_metadata else None

        # 创建视频对象
        video = DetectedVideo(
            id=video_id,
            url=url,
            title=title,
            duration=cached_metadata.duration if cached_metadata else None,
            resolution=cached_metadata.resolution if cached_metadata else None,
            filesize=cached_metadata.filesize if cached_metadata else None,
            thumbnail=thumbnail,
            detected_at=datetime.now(),
            encryption_type=self._infer_encryption_type(url, decryption_key),
            decryption_key=decryption_key,
        )

        # 添加到列表
        if self.add_detected_video(video):
            logger.info(f"Manually added video: {url}")
            return video
        else:
            logger.info(f"Video already exists: {url}")
            return None

    def _is_port_available(self, port: int) -> bool:
        """检查端口是否可用

        Args:
            port: 端口号

        Returns:
            端口可用返回 True
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    def _start_port_cache_refresh_thread(self) -> None:
        """启动后台端口-进程缓存刷新线程，避免在 mitmproxy 回调中调用 psutil。"""
        if self._port_cache_refresh_thread and self._port_cache_refresh_thread.is_alive():
            return
        self._port_cache_refresh_stop.clear()
        # 先做一次同步刷新，避免启动后前 2 秒缓存为空
        self._port_cache_refresh_once()
        self._port_cache_refresh_thread = Thread(
            target=self._port_cache_refresh_loop, daemon=True, name="port-cache-refresh"
        )
        self._port_cache_refresh_thread.start()

    def _stop_port_cache_refresh_thread(self) -> None:
        """停止后台端口-进程缓存刷新线程。"""
        self._port_cache_refresh_stop.set()
        if self._port_cache_refresh_thread and self._port_cache_refresh_thread.is_alive():
            self._port_cache_refresh_thread.join(timeout=3.0)
        self._port_cache_refresh_thread = None

    def _port_cache_refresh_once(self) -> None:
        """执行一次端口-进程缓存刷新。"""
        try:
            import psutil
        except ImportError:
            return

        try:
            connections = None
            for kind in ("inet", "tcp"):
                try:
                    connections = psutil.net_connections(kind=kind)
                    break
                except Exception:
                    continue

            if connections is not None:
                now = time.monotonic()
                refreshed: Dict[int, Tuple[Optional[str], Optional[int], float]] = {}
                for conn in connections:
                    laddr = getattr(conn, "laddr", None)
                    pid = getattr(conn, "pid", None)
                    if not laddr or not pid:
                        continue
                    local_port = getattr(laddr, "port", None)
                    if local_port is None and isinstance(laddr, tuple) and len(laddr) >= 2:
                        local_port = laddr[1]
                    if not isinstance(local_port, int):
                        continue
                    process_name: Optional[str] = None
                    try:
                        process_name = psutil.Process(pid).name()
                    except Exception:
                        pass
                    refreshed[local_port] = (process_name, pid, now)

                with self._port_process_cache_lock:
                    self._port_process_cache.update(refreshed)
        except Exception:
            logger.debug("端口缓存刷新异常", exc_info=True)

    def _port_cache_refresh_loop(self) -> None:
        """后台定期刷新端口-进程映射缓存。"""
        while not self._port_cache_refresh_stop.is_set():
            self._port_cache_refresh_once()
            # 每 2 秒刷新一次
            self._port_cache_refresh_stop.wait(timeout=2.0)

    def _lookup_process_info_by_client_port(self, client_port: Optional[int]) -> Tuple[Optional[str], Optional[int]]:
        """从缓存中查找端口对应的进程信息（不再内联调用 psutil）。"""
        if not isinstance(client_port, int) or client_port <= 0:
            return None, None

        with self._port_process_cache_lock:
            cached = self._port_process_cache.get(client_port)
            if cached:
                return cached[0], cached[1]

        return None, None

    def _lookup_process_name_by_client_port(self, client_port: Optional[int]) -> Optional[str]:
        process_name, _ = self._lookup_process_info_by_client_port(client_port)
        return process_name


class VideoSnifferAddon:
    """mitmproxy 插件，用于嗅探视频 URL

    集成 VideoURLExtractor 进行统一的URL模式匹配。
    """

    def __init__(self, sniffer: ProxySniffer):
        self.sniffer = sniffer
        self.sniffer._video_sniffer_addon = self
        self.request_count = 0
        self.flow_count = 0
        self.error_count = 0
        # 使用 sniffer 的 VideoURLExtractor 实例
        self._video_url_extractor = sniffer.get_video_url_extractor()
        self._ech_handler = ECHHandler()
        # 元数据缓存：存储从 API 响应中提取的元数据
        self._metadata_cache: Dict[str, VideoMetadata] = {}
        self._metadata_cache_lock = Lock()
        self._metadata_cache_timestamps: Dict[str, float] = {}  # 缓存条目的写入时间戳
        self._inject_script_cache: Optional[str] = None
        self._last_html_injection_at: Optional[datetime] = None
        self._page_prefetch_lock = Lock()
        self._recent_page_prefetches: Dict[str, float] = {}
        # 视频 URL 去重：避免同一视频的 Range 分段请求被重复完整处理
        self._recent_video_ids: Dict[str, float] = {}  # video_id -> 首次检测时间
        self._recent_video_ids_lock = Lock()
        # Bridge 请求去重：避免 JS 注入端洪泛导致 GIL 竞争
        self._recent_bridge_ids: Dict[str, float] = {}  # stable_id -> 最后处理时间
        self._recent_bridge_ids_lock = Lock()
        self._BRIDGE_DEDUP_WINDOW = 2.0  # 同一视频的 bridge 请求去重窗口（秒）

    def cache_external_metadata(self, metadata: VideoMetadata, cache_keys: List[str]) -> None:
        """Merge externally supplied metadata into the shared cache."""
        if not cache_keys:
            return

        normalized_cache_keys = self.sniffer._normalize_metadata_cache_keys(cache_keys)
        if not normalized_cache_keys:
            return

        normalized_title = self.sniffer._sanitize_video_title(metadata.title)
        normalized_thumbnail = self.sniffer._extract_thumbnail_url(metadata.thumbnail)
        normalized_decode_key = self.sniffer._normalize_decode_key(metadata.decode_key)
        normalized_author = str(metadata.author).strip() if metadata.author else None
        normalized_resolution = metadata.resolution
        if not normalized_resolution and metadata.width is not None and metadata.height is not None:
            normalized_resolution = f"{metadata.width}x{metadata.height}"

        with self._metadata_cache_lock:
            now = time.time()
            for cache_key in normalized_cache_keys:
                self._metadata_cache_timestamps[cache_key] = now
                existing = self._metadata_cache.get(cache_key)
                if existing:
                    preferred_title = self.sniffer._pick_better_title(existing.title, normalized_title)
                    if preferred_title:
                        existing.title = preferred_title
                    if metadata.duration is not None:
                        existing.duration = metadata.duration
                    if normalized_resolution:
                        existing.resolution = normalized_resolution
                    if metadata.filesize is not None:
                        existing.filesize = metadata.filesize
                    if normalized_thumbnail:
                        existing.thumbnail = normalized_thumbnail
                    if metadata.width is not None:
                        existing.width = metadata.width
                    if metadata.height is not None:
                        existing.height = metadata.height
                    if normalized_decode_key:
                        existing.decode_key = normalized_decode_key
                    if normalized_author:
                        existing.author = normalized_author
                else:
                    self._metadata_cache[cache_key] = VideoMetadata(
                        title=normalized_title,
                        duration=metadata.duration,
                        resolution=normalized_resolution,
                        filesize=metadata.filesize,
                        thumbnail=normalized_thumbnail,
                        width=metadata.width,
                        height=metadata.height,
                        decode_key=normalized_decode_key,
                        author=normalized_author,
                    )

        self.sniffer.reconcile_cached_metadata(normalized_cache_keys)

    def _find_recent_cached_metadata(self, max_age_seconds: float = 10.0) -> Optional[VideoMetadata]:
        """在精确键匹配失败时，返回最近缓存的有效元数据作为 fallback。

        仅返回在 max_age_seconds 秒内缓存且包含 title 或 thumbnail 的条目。
        """
        now = time.time()
        best: Optional[VideoMetadata] = None
        best_ts: float = 0.0

        with self._metadata_cache_lock:
            for cache_key, metadata in self._metadata_cache.items():
                ts = self._metadata_cache_timestamps.get(cache_key, 0.0)
                if now - ts > max_age_seconds:
                    continue
                if not metadata.title and not metadata.thumbnail:
                    continue
                if ts > best_ts:
                    best = metadata
                    best_ts = ts

        if best:
            logger.info(
                "Fallback: 使用最近 %.1fs 内缓存的元数据: title=%s, thumbnail=%s",
                now - best_ts,
                best.title,
                "yes" if best.thumbnail else "no",
            )
        return best

    @classmethod
    def _metadata_is_related(
        cls,
        baseline: Optional[VideoMetadata],
        candidate: Optional[VideoMetadata],
    ) -> bool:
        if not baseline or not candidate:
            return False

        baseline_title = ProxySniffer._sanitize_video_title(baseline.title)
        candidate_title = ProxySniffer._sanitize_video_title(candidate.title)
        baseline_thumb = ProxySniffer._extract_thumbnail_url(baseline.thumbnail)
        candidate_thumb = ProxySniffer._extract_thumbnail_url(candidate.thumbnail)
        baseline_author = str(baseline.author).strip() if baseline.author else None
        candidate_author = str(candidate.author).strip() if candidate.author else None

        title_matches = bool(
            baseline_title and candidate_title and baseline_title == candidate_title
        )
        thumbnail_matches = bool(
            baseline_thumb and candidate_thumb and baseline_thumb == candidate_thumb
        )
        author_matches = bool(
            baseline_author and candidate_author and baseline_author == candidate_author
        )

        if not any([title_matches, thumbnail_matches, author_matches]):
            return False

        if (
            baseline.duration is not None
            and candidate.duration is not None
            and abs(int(baseline.duration) - int(candidate.duration)) > 1
        ):
            return False
        if baseline.resolution and candidate.resolution and baseline.resolution != candidate.resolution:
            return False
        if baseline_thumb and candidate_thumb and baseline_thumb != candidate_thumb and not title_matches:
            return False

        return True

    @classmethod
    def _merge_metadata_candidates(cls, entries: List[VideoMetadata]) -> Optional[VideoMetadata]:
        if not entries:
            return None

        merged = VideoMetadata()
        for metadata in entries:
            preferred_title = ProxySniffer._pick_better_title(merged.title, metadata.title)
            if preferred_title:
                merged.title = preferred_title
            if metadata.duration is not None:
                merged.duration = metadata.duration
            if metadata.resolution:
                merged.resolution = metadata.resolution
            if metadata.filesize is not None:
                merged.filesize = metadata.filesize
            if metadata.thumbnail:
                merged.thumbnail = metadata.thumbnail
            if metadata.width is not None:
                merged.width = metadata.width
            if metadata.height is not None:
                merged.height = metadata.height
            if metadata.decode_key:
                merged.decode_key = metadata.decode_key
            if metadata.author:
                merged.author = metadata.author

        merged.title = ProxySniffer._sanitize_video_title(merged.title)
        merged.thumbnail = ProxySniffer._extract_thumbnail_url(merged.thumbnail)
        merged.decode_key = ProxySniffer._normalize_decode_key(merged.decode_key)
        if not merged.resolution and merged.width and merged.height:
            merged.resolution = f"{merged.width}x{merged.height}"

        if not any(
            [
                merged.title,
                merged.duration,
                merged.resolution,
                merged.filesize,
                merged.thumbnail,
                merged.decode_key,
                merged.author,
            ]
        ):
            return None

        return merged

    def _find_related_recent_cached_metadata(
        self,
        *,
        max_age_seconds: float = 10.0,
        baseline: Optional[VideoMetadata] = None,
    ) -> Optional[VideoMetadata]:
        """Return recent cached metadata, preferring entries related to the current video."""
        now = time.time()
        candidates: Dict[int, Dict[str, Any]] = {}

        with self._metadata_cache_lock:
            for cache_key, metadata in self._metadata_cache.items():
                ts = self._metadata_cache_timestamps.get(cache_key, 0.0)
                if now - ts > max_age_seconds:
                    continue
                if not any(
                    [
                        metadata.title,
                        metadata.thumbnail,
                        metadata.decode_key,
                        metadata.duration is not None,
                        metadata.filesize is not None,
                    ]
                ):
                    continue

                existing_bucket = candidates.get(id(metadata))
                if not existing_bucket:
                    candidates[id(metadata)] = {"metadata": metadata, "timestamp": ts}
                    continue
                if ts > existing_bucket["timestamp"]:
                    existing_bucket["timestamp"] = ts

        if not candidates:
            return None

        recent_candidates = list(candidates.values())
        related_entries = []
        if baseline:
            related_entries = [
                entry for entry in recent_candidates
                if self._metadata_is_related(baseline, entry["metadata"])
            ]

        if not related_entries:
            # 没有与 baseline 相关的缓存条目 → 直接放弃。
            # 不能回退到"最近的任意缓存"，否则会把其他视频的元数据
            # 泄漏给完全不相关的新视频，导致标题/缩略图相同被误合并。
            logger.debug("Fallback: 无匹配的相关缓存条目，跳过回退")
            return None

        related_entries.sort(key=lambda entry: entry["timestamp"])
        merged = self._merge_metadata_candidates([entry["metadata"] for entry in related_entries])
        if merged:
            newest_ts = related_entries[-1]["timestamp"]
            logger.info(
                "Fallback: 使用最近 %.1fs 内缓存的元数据: title=%s, thumbnail=%s, decodeKey=%s, related=%s",
                now - newest_ts,
                merged.title,
                "yes" if merged.thumbnail else "no",
                "yes" if merged.decode_key else "no",
                len(related_entries),
            )
        return merged

    def _get_inject_script_source(self) -> str:
        if self._inject_script_cache is None:
            script_path = self._resolve_inject_script_path()
            self._inject_script_cache = script_path.read_text(encoding="utf-8")

        return self._inject_script_cache

    @staticmethod
    def _resolve_inject_script_path() -> Path:
        candidate_paths: List[Path] = [
            Path(__file__).with_name("inject_script.js"),
            Path.cwd() / "backend" / "src" / "core" / "channels" / "inject_script.js",
        ]

        meipass_root = getattr(sys, "_MEIPASS", None)
        if meipass_root:
            candidate_paths.append(
                Path(meipass_root) / "src" / "core" / "channels" / "inject_script.js"
            )

        executable = getattr(sys, "executable", None)
        if executable:
            executable_dir = Path(executable).resolve().parent
            candidate_paths.append(
                executable_dir / "_internal" / "src" / "core" / "channels" / "inject_script.js"
            )

        seen_paths = set()
        for candidate in candidate_paths:
            normalized_candidate = str(candidate.resolve()) if candidate.exists() else str(candidate)
            if normalized_candidate in seen_paths:
                continue
            seen_paths.add(normalized_candidate)
            if candidate.is_file():
                return candidate

        raise FileNotFoundError(
            "Channels inject script not found. Checked: "
            + ", ".join(str(path) for path in candidate_paths)
        )

    def _get_inject_script_tag(self) -> str:
        # Inline the hook so Channels pages do not depend on a follow-up script fetch.
        script_source = self._get_inject_script_source().replace("</script", "<\\/script")
        return f'<script data-vidflow-injected="inline">\n{script_source}\n</script>'

    @staticmethod
    def _strip_html_csp_meta_tags(html: str) -> str:
        if not html:
            return html

        patterns = [
            r"<meta\b[^>]*http-equiv\s*=\s*['\"]Content-Security-Policy(?:-Report-Only)?['\"][^>]*>\s*",
            r"<meta\b[^>]*content-security-policy[^>]*>\s*",
        ]
        cleaned = html
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned

    def _mark_html_injection(self) -> None:
        self._last_html_injection_at = datetime.now()

    def _has_recent_html_injection(self, max_age_seconds: int = 120) -> bool:
        if not self._last_html_injection_at:
            return False

        age_seconds = (datetime.now() - self._last_html_injection_at).total_seconds()
        if age_seconds > max_age_seconds:
            self._last_html_injection_at = None
            return False
        return True

    def _lookup_process_info_by_client_port(self, client_port: Optional[int]) -> Tuple[Optional[str], Optional[int]]:
        """委托给 ProxySniffer 的缓存查找。"""
        return self.sniffer._lookup_process_info_by_client_port(client_port)

    def _lookup_process_name_by_client_port(self, client_port: Optional[int]) -> Optional[str]:
        return self.sniffer._lookup_process_name_by_client_port(client_port)

    @staticmethod
    def _read_request_text(flow) -> str:
        request = getattr(flow, "request", None)
        if not request:
            return ""

        try:
            if hasattr(request, "get_text"):
                text = request.get_text(strict=False)
                if isinstance(text, str):
                    return text
        except Exception:
            logger.debug("Failed to read request text via get_text", exc_info=True)

        try:
            text = getattr(request, "text", None)
            if isinstance(text, str):
                return text
        except Exception:
            logger.debug("Failed to read request.text", exc_info=True)

        try:
            content = bytes(getattr(request, "content", b"") or b"")
            if content:
                return content.decode("utf-8", errors="ignore")
        except Exception:
            logger.debug("Failed to decode request body", exc_info=True)

        return ""

    @staticmethod
    def _get_client_port_from_flow(flow) -> Optional[int]:
        client_conn = getattr(flow, "client_conn", None)
        if not client_conn:
            return None

        peername = getattr(client_conn, "peername", None)
        if isinstance(peername, tuple) and len(peername) >= 2 and isinstance(peername[1], int):
            return peername[1]

        return None

    @staticmethod
    def _is_channels_script_asset(url: str, content_type: str) -> bool:
        try:
            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            path = (parsed.path or "").lower()
        except Exception:
            return False

        if not VideoSnifferAddon._is_supported_channels_asset_host(host):
            return False

        content_type_lower = (content_type or "").lower()
        if any(token in content_type_lower for token in ["javascript", "ecmascript"]):
            return True

        return path.endswith((".js", ".mjs"))

    @staticmethod
    def _is_supported_channels_inject_host(host: str) -> bool:
        host_lower = (host or "").lower()
        return any(domain in host_lower for domain in CHANNELS_INJECT_HTML_HOSTS)

    @staticmethod
    def _is_supported_channels_asset_host(host: str) -> bool:
        host_lower = (host or "").lower()
        return any(domain in host_lower for domain in CHANNELS_INJECT_ASSET_HOSTS)

    @staticmethod
    def _is_supported_channels_page_request(host: str, path: str) -> bool:
        host_lower = (host or "").lower()
        path_lower = ((path or "").lower() or "/").split("?", 1)[0]

        if path_lower.endswith(CHANNELS_STATIC_PATH_SUFFIXES):
            return False

        if "channels.weixin.qq.com" in host_lower:
            return path_lower.startswith(("/web/", "/platform/")) or path_lower in {"", "/"}

        if "wxa.wxs.qq.com" in host_lower:
            return "base_tmpl.html" in path_lower or path_lower.endswith(".html") or "/tmpl/pf/" in path_lower

        if any(domain in host_lower for domain in ["servicewechat.com", "liteapp.weixin.qq.com"]):
            return path_lower not in {"/favicon.ico", "/robots.txt"}

        return False

    @classmethod
    def _normalize_prefetch_page_candidate(cls, value: Any) -> str:
        candidate = unescape(unquote(str(value or "").strip()))
        if not candidate:
            return ""

        try:
            parsed = urlparse(candidate)
        except Exception:
            return ""

        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        host = (netloc or "").lower()
        path = parsed.path or "/"
        query = parsed.query
        fragment = parsed.fragment

        if not cls._is_supported_channels_inject_host(host):
            return ""

        path_lower = path.lower()
        if "channels.weixin.qq.com" in host:
            if path_lower in {"", "/", "/web", "/web/"} or path_lower.startswith("/web/report"):
                path = "/web/pages/home"
                query = ""
                fragment = ""
            elif path_lower.startswith("/web/") and not path_lower.startswith("/web/pages/"):
                path = "/web/pages/home"
                query = ""
                fragment = ""
        elif "wxa.wxs.qq.com" in host and path_lower in {"", "/"}:
            path = "/tmpl/pf/base_tmpl.html"
            query = ""
            fragment = ""

        if not cls._is_supported_channels_page_request(host, path):
            return ""

        return urlunparse((scheme, netloc, path, parsed.params, query, fragment))

    def _extract_prefetch_page_url(self, flow, evidence_url: str = "") -> Optional[str]:
        candidates: List[str] = []
        request = getattr(flow, "request", None)
        headers = getattr(request, "headers", None)

        def add_candidate(value: Any) -> None:
            candidate = self._normalize_prefetch_page_candidate(value)
            if not candidate or candidate in candidates:
                return
            candidates.append(candidate)

        if hasattr(headers, "get"):
            add_candidate(headers.get("Referer"))

        request_text = self._read_request_text(flow)
        if request_text:
            for pattern in (
                r'"pageUrl"\s*:\s*"([^"]+)"',
                r'"referer"\s*:\s*"([^"]+)"',
                r"(?:^|[?&])pageUrl=([^&]+)",
                r"(?:^|[?&])referer=([^&]+)",
            ):
                for match in re.finditer(pattern, request_text, flags=re.IGNORECASE):
                    add_candidate(match.group(1))

        if hasattr(headers, "get"):
            add_candidate(headers.get("Origin"))

        add_candidate(evidence_url)
        if request is not None:
            add_candidate(getattr(request, "pretty_url", ""))

        return candidates[0] if candidates else None

    def _build_page_prefetch_headers(self, flow, page_url: str) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": page_url,
        }

        request = getattr(flow, "request", None)
        request_headers = getattr(request, "headers", None)
        if hasattr(request_headers, "get"):
            for header_name in ("User-Agent", "Cookie", "Accept-Language"):
                header_value = request_headers.get(header_name)
                if header_value:
                    headers[header_name] = str(header_value)
            origin = request_headers.get("Origin")
            if origin:
                headers["Origin"] = str(origin)

        if "User-Agent" not in headers:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
                "MicroMessenger/7.0.20.1781(0x6700143B)"
            )

        return headers

    def _fetch_page_document(
        self,
        page_url: str,
        headers: Dict[str, str],
    ) -> Tuple[Optional[int], str, str]:
        request = urllib_request.Request(page_url, headers=headers, method="GET")
        opener = urllib_request.build_opener(urllib_request.ProxyHandler({}))
        with opener.open(request, timeout=CHANNELS_PAGE_PREFETCH_TIMEOUT_SECONDS) as response:
            status_code = getattr(response, "status", None)
            if not isinstance(status_code, int):
                try:
                    status_code = int(response.getcode())
                except Exception:
                    status_code = None

            content_type = response.headers.get("Content-Type", "")
            body = response.read(CHANNELS_PAGE_PREFETCH_MAX_BYTES + 1)
            if len(body) > CHANNELS_PAGE_PREFETCH_MAX_BYTES:
                body = body[:CHANNELS_PAGE_PREFETCH_MAX_BYTES]

            charset = None
            try:
                charset = response.headers.get_content_charset()
            except Exception:
                charset = None
            text = body.decode(charset or "utf-8", errors="ignore")
            return status_code, content_type, text

    def _prefetch_page_metadata(
        self,
        page_url: str,
        headers: Dict[str, str],
        evidence_url: str,
    ) -> None:
        try:
            status_code, content_type, response_text = self._fetch_page_document(page_url, headers)
        except urllib_error.HTTPError as exc:
            self.sniffer.record_relevant_response(
                page_url,
                exc.headers.get("Content-Type", "") if getattr(exc, "headers", None) else "",
                exc.code,
                "channels_page_prefetch_skip",
                f"http_error:{exc.code}",
            )
            return
        except Exception:
            logger.debug("Failed to prefetch Channels page metadata: %s", page_url, exc_info=True)
            self.sniffer.record_relevant_response(
                page_url,
                "",
                None,
                "channels_page_prefetch_skip",
                "request_failed",
            )
            return

        if not self._looks_like_html_document(page_url, content_type, response_text):
            self.sniffer.record_relevant_response(
                page_url,
                content_type,
                status_code,
                "channels_page_prefetch_skip",
                "not_html_like",
            )
            return

        candidates = self._extract_text_response_candidates(page_url, response_text)
        if not candidates:
            self.sniffer.record_relevant_response(
                page_url,
                content_type,
                status_code,
                "channels_page_prefetch_skip",
                "no_metadata_candidates",
            )
            return

        for candidate in candidates:
            self.cache_external_metadata(candidate["metadata"], candidate["cache_keys"])
            metadata = candidate["metadata"]
            logger.info(
                "Cached metadata from prefetched Channels page: title=%s, thumbnail=%s, decodeKey=%s, url=%s",
                metadata.title,
                "yes" if metadata.thumbnail else "no",
                "yes" if metadata.decode_key else "no",
                (candidate["url"] or page_url)[:120],
            )

        self.sniffer.record_relevant_response(
            page_url,
            content_type,
            status_code,
            "channels_page_prefetch_hit",
            f"evidence={str(evidence_url or page_url)[:96]} candidates={len(candidates)}",
        )

    def _schedule_page_metadata_prefetch(self, flow, evidence_url: str = "") -> bool:
        if self.sniffer.has_channels_page_injection():
            return False

        page_url = self._extract_prefetch_page_url(flow, evidence_url=evidence_url)
        if not page_url:
            return False

        now = time.monotonic()
        with self._page_prefetch_lock:
            stale_urls = [
                cached_url
                for cached_url, prefetched_at in self._recent_page_prefetches.items()
                if now - prefetched_at > CHANNELS_PAGE_PREFETCH_COOLDOWN_SECONDS
            ]
            for stale_url in stale_urls:
                self._recent_page_prefetches.pop(stale_url, None)
            if page_url in self._recent_page_prefetches:
                return False
            self._recent_page_prefetches[page_url] = now

        headers = self._build_page_prefetch_headers(flow, page_url)
        Thread(
            target=self._prefetch_page_metadata,
            args=(page_url, headers, evidence_url or page_url),
            daemon=True,
            name="VidFlowChannelsPagePrefetch",
        ).start()
        self.sniffer.record_relevant_response(
            page_url,
            "",
            None,
            "channels_page_prefetch_scheduled",
            f"evidence={str(evidence_url or page_url)[:96]}",
        )
        return True

    @staticmethod
    def _is_channels_inject_proxy_request(flow) -> bool:
        try:
            parsed = urlparse(flow.request.pretty_url)
        except Exception:
            return False

        return (
            VideoSnifferAddon._is_supported_channels_inject_host(parsed.netloc or "")
            and parsed.path == CHANNELS_INJECT_PROXY_PATH
        )

    @staticmethod
    def _is_channels_inject_script_request(flow) -> bool:
        try:
            parsed = urlparse(flow.request.pretty_url)
        except Exception:
            return False

        return (
            VideoSnifferAddon._is_supported_channels_inject_host(parsed.netloc or "")
            and parsed.path == CHANNELS_INJECT_SCRIPT_PATH
        )

    @staticmethod
    def _build_proxy_ingest_response(
        status_code: int,
        payload: Optional[Dict[str, Any]] = None,
        origin: Optional[str] = None,
    ):
        from mitmproxy import http

        headers = {
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        }
        if payload is None:
            content = b""
        else:
            headers["Content-Type"] = "application/json; charset=utf-8"
            content = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        if origin:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            headers["Access-Control-Allow-Headers"] = "Content-Type"
            headers["Vary"] = "Origin"

        return http.Response.make(status_code, content, headers)

    def _handle_channels_inject_script_request(self, flow) -> bool:
        if not self._is_channels_inject_script_request(flow):
            return False

        from mitmproxy import http

        flow.metadata["vidflow_internal_request"] = "channels_inject_script"
        flow.response = http.Response.make(
            200,
            self._get_inject_script_source().encode("utf-8"),
            {
                "Content-Type": "application/javascript; charset=utf-8",
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )
        return True

    def _handle_channels_inject_proxy_request(self, flow) -> bool:
        if not self._is_channels_inject_proxy_request(flow):
            return False

        origin = flow.request.headers.get("Origin")
        method = (flow.request.method or "GET").upper()
        flow.metadata["vidflow_internal_request"] = "channels_inject"

        if method == "OPTIONS":
            flow.response = self._build_proxy_ingest_response(204, origin=origin)
            return True

        if method != "POST":
            flow.response = self._build_proxy_ingest_response(
                405,
                {"success": False, "detail": "Method not allowed"},
                origin=origin,
            )
            return True

        try:
            body_text = ""
            if hasattr(flow.request, "get_text"):
                body_text = flow.request.get_text(strict=False) or ""
            elif getattr(flow.request, "text", None):
                body_text = flow.request.text
            payload = json.loads(body_text or "{}")
        except json.JSONDecodeError:
            flow.response = self._build_proxy_ingest_response(
                400,
                {"success": False, "detail": "Invalid JSON payload"},
                origin=origin,
            )
            return True
        except Exception:
            logger.debug("Failed to read injected metadata request body", exc_info=True)
            flow.response = self._build_proxy_ingest_response(
                400,
                {"success": False, "detail": "Failed to read request body"},
                origin=origin,
            )
            return True

        def _as_int(value: Any) -> Optional[int]:
            if value is None or value == "":
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        normalized_url = ChannelsDownloader._normalize_video_url(str(payload.get("url") or "").strip())
        page_url = str(payload.get("pageUrl") or "").strip() or None
        raw_title = str(payload.get("title") or "").strip()
        provided_cache_keys = self.sniffer._normalize_metadata_cache_keys(payload.get("cacheKeys"))
        for cache_key in self.sniffer._build_metadata_cache_keys(page_url):
            if cache_key not in provided_cache_keys:
                provided_cache_keys.append(cache_key)

        duration = _as_int(payload.get("duration"))
        width = _as_int(payload.get("videoWidth"))
        height = _as_int(payload.get("videoHeight"))
        filesize = _as_int(payload.get("fileSize"))
        decode_key = self.sniffer._normalize_decode_key(
            payload.get("decodeKey")
            or payload.get("decode_key")
            or payload.get("decodeKey64")
            or payload.get("decode_key64")
            or payload.get("decryptKey")
            or payload.get("decrypt_key")
            or payload.get("decryptionKey")
            or payload.get("decryption_key")
            or payload.get("decryptSeed")
            or payload.get("decrypt_seed")
            or payload.get("seed")
            or payload.get("seedValue")
            or payload.get("seed_value")
            or payload.get("mediaKey")
            or payload.get("media_key")
            or payload.get("videoKey")
            or payload.get("video_key")
        )
        cache_key_preview = ",".join(provided_cache_keys[:4]) if provided_cache_keys else "none"
        title_preview = raw_title[:80] if raw_title else "no"

        # Bridge 请求去重：基于 cache keys 或 URL 的稳定标识
        bridge_stable_id = None
        if provided_cache_keys:
            bridge_stable_id = "cache:" + ",".join(sorted(provided_cache_keys[:4]))
        elif normalized_url:
            # 从 URL 中提取 encfilekey 作为稳定 ID
            import re
            enc_match = re.search(r'[?&]encfilekey=([^&]{10,40})', normalized_url)
            if enc_match:
                bridge_stable_id = "enc:" + enc_match.group(1)
            else:
                # 用 URL path 部分
                path_match = re.match(r'https?://[^?#]+', normalized_url)
                bridge_stable_id = "url:" + (path_match.group(0)[:120] if path_match else normalized_url[:120])

        if bridge_stable_id:
            now = time.time()
            with self._recent_bridge_ids_lock:
                last_seen = self._recent_bridge_ids.get(bridge_stable_id)
                has_new_info = bool(raw_title and not (last_seen and self._recent_bridge_ids.get(bridge_stable_id + ":title")))
                if not has_new_info and decode_key and not self._recent_bridge_ids.get(bridge_stable_id + ":dk"):
                    has_new_info = True
                if last_seen and (now - last_seen) < self._BRIDGE_DEDUP_WINDOW and not has_new_info:
                    logger.debug("跳过重复 bridge 请求: %s (%.1fs 内)", bridge_stable_id[:60], now - last_seen)
                    flow.response = self._build_proxy_ingest_response(
                        200, {"success": True, "detail": "deduplicated"}, origin=origin
                    )
                    return True
                self._recent_bridge_ids[bridge_stable_id] = now
                if raw_title:
                    self._recent_bridge_ids[bridge_stable_id + ":title"] = now
                if decode_key:
                    self._recent_bridge_ids[bridge_stable_id + ":dk"] = now
                # 清理过期条目
                expired = [k for k, v in self._recent_bridge_ids.items() if (now - v) > 30.0]
                for k in expired:
                    del self._recent_bridge_ids[k]

        logger.info(
            "Channels proxy bridge request: url=%s cacheKeys=%s preview=%s title=%s titlePreview=%s thumb=%s decodeKey=%s page=%s",
            "yes" if normalized_url else "no",
            len(provided_cache_keys),
            cache_key_preview,
            "yes" if raw_title else "no",
            title_preview,
            "yes" if payload.get("thumbnail") else "no",
            "yes" if decode_key else "no",
            page_url[:120] if page_url else "no",
        )

        if not normalized_url and not provided_cache_keys:
            logger.warning("Channels proxy bridge rejected payload without URL or cache keys")
            flow.response = self._build_proxy_ingest_response(
                400,
                {"success": False, "detail": "Missing valid video URL or metadata cache keys"},
                origin=origin,
            )
            return True

        if not normalized_url:
            resolution = None
            if width and height and width > 0 and height > 0:
                resolution = f"{width}x{height}"

            metadata = VideoMetadata(
                title=self.sniffer._sanitize_video_title(payload.get("title")),
                duration=duration,
                resolution=resolution,
                filesize=filesize,
                thumbnail=str(payload.get("thumbnail")).strip() if payload.get("thumbnail") else None,
                width=width,
                height=height,
                decode_key=decode_key,
                author=str(payload.get("author")).strip() if payload.get("author") else None,
            )
            self.cache_external_metadata(metadata, provided_cache_keys)
            logger.info(
                "Injected channels metadata cached via proxy without URL: title=%s thumb=%s decodeKey=%s cacheKeys=%s",
                metadata.title,
                "yes" if metadata.thumbnail else "no",
                "yes" if metadata.decode_key else "no",
                len(provided_cache_keys),
            )
            flow.response = self._build_proxy_ingest_response(
                200,
                {
                    "success": True,
                    "cached_only": True,
                    "cache_keys": provided_cache_keys,
                },
                origin=origin,
            )
            return True

        try:
            video = self.sniffer.ingest_injected_video(
                url=normalized_url,
                title=payload.get("title"),
                thumbnail=payload.get("thumbnail"),
                duration=duration,
                width=width,
                height=height,
                filesize=filesize,
                decode_key=decode_key,
                page_url=page_url,
                extra_cache_keys=provided_cache_keys,
            )
        except Exception:
            logger.exception("Error ingesting channels metadata via proxy bridge")
            flow.response = self._build_proxy_ingest_response(
                500,
                {"success": False, "detail": "Failed to ingest video metadata"},
                origin=origin,
            )
            return True

        if video is None:
            flow.response = self._build_proxy_ingest_response(
                500,
                {"success": False, "detail": "Video metadata ingestion returned no record"},
                origin=origin,
            )
            return True

        logger.info(
            "Injected channels metadata accepted via proxy: title=%s thumb=%s decodeKey=%s",
            video.title,
            "yes" if video.thumbnail else "no",
            "yes" if video.decryption_key else "no",
        )
        flow.response = self._build_proxy_ingest_response(
            200,
            {"success": True, "video": video.to_dict()},
            origin=origin,
        )
        return True

    def _inject_channels_script(self, flow) -> bool:
        """Inject the VidFlow metadata hook into WeChat Channels HTML pages."""
        try:
            content_type = flow.response.headers.get("Content-Type", "")
            url = flow.request.pretty_url
            status_code = getattr(flow.response, "status_code", None)
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            path = (parsed.path or "").lower()
            if not self._is_supported_channels_inject_host(host):
                return False

            html = self._get_flow_response_text(flow)
            if not self._looks_like_html_document(url, content_type, html):
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    status_code,
                    "channels_html_skip",
                    "not_html_like",
                )
                return False
            if not self._is_supported_channels_page_request(host, path):
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    status_code,
                    "channels_html_skip",
                    f"unsupported_path:{path or '/'}",
                )
                return False
            if not html:
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    status_code,
                    "channels_html_skip",
                    "empty_body",
                )
                return False
            if "__vidflow_injected__" in html or CHANNELS_INJECT_SCRIPT_PATH in html:
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    status_code,
                    "channels_html_skip",
                    "already_injected",
                )
                return False

            self.sniffer.record_relevant_response(
                url,
                content_type,
                status_code,
                "channels_html_candidate",
                f"host={host} path={path or '/'}",
            )
            html = self._strip_html_csp_meta_tags(html)
            snippet = self._get_inject_script_tag()
            lower_html = html.lower()
            if "</body>" in lower_html:
                html = html.replace("</body>", f"{snippet}</body>", 1)
            elif "</head>" in lower_html:
                html = html.replace("</head>", f"{snippet}</head>", 1)
            elif "<script" in lower_html:
                script_index = lower_html.find("<script")
                html = f"{html[:script_index]}{snippet}{html[script_index:]}"
            elif "<body" in lower_html:
                body_open_index = lower_html.find("<body")
                body_tag_end = lower_html.find(">", body_open_index)
                if body_tag_end != -1:
                    html = f"{html[:body_tag_end + 1]}{snippet}{html[body_tag_end + 1:]}"
                else:
                    html = f"{html}{snippet}"
            elif "<head" in lower_html:
                head_open_index = lower_html.find("<head")
                head_tag_end = lower_html.find(">", head_open_index)
                if head_tag_end != -1:
                    html = f"{html[:head_tag_end + 1]}{snippet}{html[head_tag_end + 1:]}"
                else:
                    html = f"{snippet}{html}"
            else:
                html = f"{snippet}{html}"

            flow.response.set_text(html)
            for header in [
                "Content-Security-Policy",
                "Content-Security-Policy-Report-Only",
                "X-Content-Security-Policy",
                "X-WebKit-CSP",
            ]:
                if header in flow.response.headers:
                    del flow.response.headers[header]
            self._mark_html_injection()
            self.sniffer.note_channels_page_injection("html", url)
            self.sniffer.record_relevant_response(
                url,
                content_type,
                status_code,
                "channels_html_injected",
            )
            logger.info(
                "Injected VidFlow channels hook into HTML: type=%s url=%s",
                content_type or "<empty>",
                url[:120],
            )
            return True
        except Exception:
            logger.debug("Failed to inject channels hook", exc_info=True)
            return False

    def _inject_channels_script_asset(self, flow) -> bool:
        """Inject the VidFlow hook into JavaScript assets when HTML shell is missed."""
        try:
            content_type = flow.response.headers.get("Content-Type", "")
            url = flow.request.pretty_url
            status_code = getattr(flow.response, "status_code", None)
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            path = (parsed.path or "").lower()
            if not self._is_channels_script_asset(url, content_type):
                if self._is_supported_channels_asset_host(host) and (
                    path.endswith((".js", ".mjs")) or "javascript" in (content_type or "").lower()
                ):
                    self.sniffer.record_relevant_response(
                        url,
                        content_type,
                        status_code,
                        "channels_js_skip",
                        "not_recognized_asset",
                    )
                return False
            if self._has_recent_html_injection():
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    status_code,
                    "channels_js_skip",
                    "html_injected_recently",
                )
                return False

            script_text = self._get_flow_response_text(flow)
            if not script_text:
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    status_code,
                    "channels_js_skip",
                    "empty_body",
                )
                return False
            if "__vidflow_injected__" in script_text or "__VIDFLOW_API_BASE__" in script_text:
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    status_code,
                    "channels_js_skip",
                    "already_injected",
                )
                return False

            injected_script = self._get_inject_script_source()
            flow.response.set_text(f"{injected_script}\n;{script_text}")
            self.sniffer.note_channels_page_injection("js", url)
            self.sniffer.record_relevant_response(
                url,
                content_type,
                status_code,
                "channels_js_injected",
            )

            logger.info(
                "Injected VidFlow channels hook into JS asset: type=%s url=%s",
                content_type or "<empty>",
                url[:120],
            )
            return True
        except Exception:
            logger.debug("Failed to inject channels JS asset", exc_info=True)
            return False

    # ------------------------------------------------------------------ #
    #  JS 函数包裹：在代理层修改微信前端 JS，包裹 API 函数以捕获返回值   #
    # ------------------------------------------------------------------ #

    # 需要包裹的微信 API 函数名列表
    _WECHAT_API_FUNCTIONS_TO_WRAP = [
        "finderPcFlow",
        "finderInit",
        "finderGetCommentDetail",
        "finderGetRecommend",
        "finderUserPage",
        "finderLiveUserPage",
        "finderSearch",
        "finderPcSearch",
        "finderStream",
        "finderGetFeedDetail",
        "finderGetFollowList",
        "finderLivePage",
    ]

    def _wrap_wechat_api_functions(self, flow) -> bool:
        """在代理层修改微信前端 JS 源码，包裹 API 函数以捕获返回值

        参考 wx_channels_download 的方案：不是 Hook XHR/fetch，而是直接
        修改微信前端 JS 中的 API 函数定义，在函数返回值中拦截 decodeKey。

        Args:
            flow: mitmproxy flow 对象

        Returns:
            是否成功包裹了至少一个函数
        """
        try:
            content_type = flow.response.headers.get("Content-Type", "")
            url = flow.request.pretty_url
            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            path = (parsed.path or "").lower()

            # 仅处理来自微信域名的 JS 文件
            if not any(d in host for d in ["channels.weixin.qq.com", "res.wx.qq.com", "wxa.wxs.qq.com"]):
                return False

            content_type_lower = (content_type or "").lower()
            is_js = any(t in content_type_lower for t in ["javascript", "ecmascript"]) or path.endswith((".js", ".mjs"))
            if not is_js:
                return False

            script_text = self._get_flow_response_text(flow)
            if not script_text or len(script_text) < 100:
                return False

            # 已经被我们处理过
            if "__vidflow_api_wrapped__" in script_text:
                return False

            wrapped_count = 0
            modified_text = script_text

            for func_name in self._WECHAT_API_FUNCTIONS_TO_WRAP:
                # 匹配多种函数定义模式（包括压缩后的代码）：
                # 1. async finderPcFlow(        — 方法速记
                # 2. async function finderPcFlow( — 命名函数声明
                # 3. finderPcFlow:async(         — 对象属性（压缩）
                # 4. finderPcFlow:async function( — 对象属性
                # 5. finderPcFlow=async(         — 赋值
                # 6. "finderPcFlow":async function( — 引号键
                patterns = [
                    # 对象属性模式（压缩代码最常见）：finderPcFlow:async function( 或 finderPcFlow:async(
                    rf'(["\']?){func_name}\1\s*:\s*async\s+function\s*(\()',
                    rf'(["\']?){func_name}\1\s*:\s*async\s*(\()',
                    # 方法速记：async finderPcFlow(
                    rf'(async\s+){func_name}(\s*\()',
                    # 命名函数声明：async function finderPcFlow(
                    rf'(async\s+function\s+){func_name}(\s*\()',
                    # 赋值模式：finderPcFlow=async function( 或 finderPcFlow=async(
                    rf'(\b){func_name}\s*=\s*async\s+function\s*(\()',
                    rf'(\b){func_name}\s*=\s*async\s*(\()',
                ]

                for pattern in patterns:
                    match = re.search(pattern, modified_text)
                    if match:
                        modified_text = self._wrap_matched_async_function(
                            modified_text, match, func_name
                        )
                        if modified_text is not None:
                            wrapped_count += 1
                            logger.info(
                                "[API_WRAP] 包裹微信 API 函数: %s (pattern=%s url=%s)",
                                func_name,
                                pattern[:50],
                                url[:80],
                            )
                            break  # 同一个函数只匹配一次
                        else:
                            # 包裹失败（找不到匹配的花括号），恢复原文本
                            modified_text = script_text
                            logger.debug(
                                "[API_WRAP] 花括号匹配失败: %s", func_name
                            )

            if wrapped_count > 0:
                # 在文件头部添加标记和辅助函数
                wrapper_header = self._get_api_wrapper_header()
                modified_text = f"{wrapper_header}\n;{modified_text}"
                flow.response.set_text(modified_text)
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    getattr(flow.response, "status_code", None),
                    "channels_js_api_wrapped",
                    f"wrapped={wrapped_count}",
                )
                logger.info(
                    "[API_WRAP] 成功包裹 %d 个 API 函数: %s",
                    wrapped_count,
                    url[:120],
                )
                return True

            return False
        except Exception:
            logger.debug("Failed to wrap WeChat API functions", exc_info=True)
            return False

    def _get_api_wrapper_header(self) -> str:
        """生成 API 包裹辅助函数的 JS 代码"""
        return """
/* __vidflow_api_wrapped__ */
(function(){
    if(window.__vidflow_api_wrapped__)return;
    window.__vidflow_api_wrapped__=true;
    var POST_PATH='/__vidflow/channels/videos/inject';
    var POST_URL=(window.location&&window.location.origin)
        ?window.location.origin+POST_PATH
        :('https://channels.weixin.qq.com'+POST_PATH);
    window.__vidflow_send_api_result__=function(funcName,result){
        try{
            if(!result||typeof result!=='object')return;
            var data=result.data||result;
            var feeds=[];
            function extractFeeds(obj,depth){
                if(!obj||typeof obj!=='object'||depth>8)return;
                if(Array.isArray(obj)){
                    for(var i=0;i<obj.length;i++)extractFeeds(obj[i],depth+1);
                    return;
                }
                var url=obj.url||obj.videoUrl||obj.video_url||obj.playUrl||obj.mediaUrl||'';
                var dk=obj.decodeKey||obj.decode_key||obj.key||obj.decryptKey||null;
                var title=obj.title||obj.desc||obj.description||obj.nickName||'';
                var thumb=obj.thumbUrl||obj.thumb_url||obj.coverUrl||obj.cover||'';
                if(url&&(url.indexOf('finder.video')!==-1||url.indexOf('findervideodownload')!==-1)){
                    feeds.push({url:url,decodeKey:dk,title:title,thumbUrl:thumb,source:'api_wrap_'+funcName});
                }
                if(obj.object||obj.objectDesc)extractFeeds(obj.object||obj.objectDesc,depth+1);
                if(obj.media)extractFeeds(obj.media,depth+1);
                if(obj.feedObject||obj.feed_object)extractFeeds(obj.feedObject||obj.feed_object,depth+1);
                if(obj.video||obj.videoInfo)extractFeeds(obj.video||obj.videoInfo,depth+1);
                var spec=obj.spec||obj.specs||obj.mediaSpec||obj.specList;
                if(spec)extractFeeds(spec,depth+1);
                var keys=Object.keys(obj);
                for(var k=0;k<keys.length;k++){
                    var v=obj[keys[k]];
                    if(v&&typeof v==='object')extractFeeds(v,depth+1);
                }
            }
            extractFeeds(data,0);
            if(feeds.length===0){
                // 即使没找到标准 feed，也尝试深度搜索 decodeKey
                var rawStr=JSON.stringify(data).substring(0,16000);
                var dkMatch=rawStr.match(/"(?:decodeKey|decode_key|key)"\\s*:\\s*"?(\\d{5,20})"?/);
                var urlMatch=rawStr.match(/(https?:\\/\\/(?:finder\\.video|findervideodownload)\\.qq\\.com\\/[^"\\\\]+)/);
                if(dkMatch||urlMatch){
                    feeds.push({
                        url:urlMatch?urlMatch[1]:null,
                        decodeKey:dkMatch?dkMatch[1]:null,
                        title:null,thumbUrl:null,
                        source:'api_wrap_raw_'+funcName
                    });
                    console.log('[VidFlow][API_WRAP] 从原始 JSON 提取: dk='+(dkMatch?dkMatch[1]:'no')+' url='+(urlMatch?'yes':'no'));
                }
            }
            for(var f=0;f<feeds.length;f++){
                var fd=feeds[f];
                console.log('[VidFlow][API_WRAP] 捕获到 '+funcName+' 返回值:','dk='+(fd.decodeKey?'yes':'no'),'url='+(fd.url||'none').substring(0,80));
                try{
                    var xhr=new XMLHttpRequest();
                    xhr.open('POST',POST_URL,true);
                    xhr.setRequestHeader('Content-Type','application/json');
                    // 发送扁平结构，匹配 InjectedVideoPayload schema
                    xhr.send(JSON.stringify({
                        url:fd.url||null,
                        title:fd.title||null,
                        decodeKey:fd.decodeKey?String(fd.decodeKey):null,
                        thumbnail:fd.thumbUrl||null,
                        source:'api_wrap_'+funcName,
                        cacheKeys:fd.url?[fd.url.split('?')[0].split('/').pop()]:[],
                        pageUrl:window.location?window.location.href:null
                    }));
                }catch(e){}
            }
        }catch(e){
            console.warn('[VidFlow][API_WRAP] Error:',e);
        }
    };
})();
"""

    def _wrap_matched_async_function(
        self, text: str, match: re.Match, func_name: str
    ) -> Optional[str]:
        """将匹配到的 async 函数包裹一层，在返回值中拦截 decodeKey

        通用包裹方法，支持所有匹配模式。

        Args:
            text: 完整的 JS 源码文本
            match: 正则匹配结果
            func_name: 函数名（用于日志和数据标识）

        Returns:
            修改后的文本，如果包裹失败返回 None
        """
        start_pos = match.start()
        # 找到参数列表后的第一个 {
        brace_pos = text.find("{", match.end())
        if brace_pos == -1:
            return None

        # 确保 { 在合理范围内（参数列表不应超过 500 字符）
        if brace_pos - match.end() > 500:
            return None

        end_pos = self._find_matching_brace(text, brace_pos)
        if end_pos == -1:
            return None

        # 提取原始函数体（不含外层花括号）
        original_body = text[brace_pos + 1:end_pos]

        # 构建包裹版本：保留原始函数签名，将函数体包裹在 IIFE 中
        matched_prefix = text[start_pos:brace_pos]
        wrapped = (
            f"{matched_prefix}"
            "{\n"
            f"  var __vf_r__ = await (async () => {{{original_body}}})();\n"
            f"  try{{ window.__vidflow_send_api_result__ && "
            f"window.__vidflow_send_api_result__('{func_name}', __vf_r__); }}"
            "catch(__vf_e__){}\n"
            "  return __vf_r__;\n"
            "}"
        )

        return text[:start_pos] + wrapped + text[end_pos + 1:]

    @staticmethod
    def _find_matching_brace(text: str, open_pos: int) -> int:
        """找到与 open_pos 处的 { 匹配的 } 的位置

        考虑字符串字面量、模板字符串、正则表达式和注释中的花括号。

        Args:
            text: 源代码文本
            open_pos: 起始 { 的位置

        Returns:
            匹配的 } 的位置，未找到返回 -1
        """
        if open_pos >= len(text) or text[open_pos] != "{":
            return -1

        depth = 1
        i = open_pos + 1
        length = len(text)

        while i < length and depth > 0:
            ch = text[i]

            # 跳过单行注释
            if ch == "/" and i + 1 < length:
                if text[i + 1] == "/":
                    i = text.find("\n", i + 2)
                    if i == -1:
                        return -1
                    i += 1
                    continue
                # 跳过多行注释
                if text[i + 1] == "*":
                    end = text.find("*/", i + 2)
                    if end == -1:
                        return -1
                    i = end + 2
                    continue

            # 跳过字符串
            if ch in ('"', "'"):
                i += 1
                while i < length:
                    if text[i] == "\\":
                        i += 2
                        continue
                    if text[i] == ch:
                        break
                    i += 1
                i += 1
                continue

            # 跳过模板字符串
            if ch == "`":
                i += 1
                template_depth = 0
                while i < length:
                    if text[i] == "\\":
                        i += 2
                        continue
                    if text[i] == "`" and template_depth == 0:
                        break
                    if text[i] == "$" and i + 1 < length and text[i + 1] == "{":
                        template_depth += 1
                        i += 2
                        continue
                    if text[i] == "}" and template_depth > 0:
                        template_depth -= 1
                    i += 1
                i += 1
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1

            i += 1

        return i - 1 if depth == 0 else -1

    def load(self, loader):
        """插件加载时调用"""
        logger.info("VideoSnifferAddon loaded")

    def running(self):
        """mitmproxy 开始运行时调用"""
        logger.info("VideoSnifferAddon running")

    def client_connected(self, client):
        """客户端连接时调用"""
        process_name = None
        process_pid = None
        if isinstance(getattr(client, "peername", None), tuple) and len(client.peername) >= 2:
            process_name, process_pid = self._lookup_process_info_by_client_port(client.peername[1])
            self.sniffer.note_renderer_process_activity(process_name, process_pid)

        if process_name:
            logger.debug("Client connected: %s process=%s", client.peername, process_name)
        else:
            logger.debug("Client connected: %s", client.peername)

    def client_disconnected(self, client):
        """客户端断开时调用"""
        logger.debug(f"Client disconnected: {client.peername}")

    def server_connect(self, data):
        """连接到服务器时调用"""
        logger.debug("Connecting to server: %s", data.server.address)

    def server_connected(self, data):
        """连接到服务器成功时调用"""
        logger.debug("Connected to server: %s", data.server.address)

    def tls_clienthello(self, data):
        """收到 TLS ClientHello 时调用"""
        try:
            sni = data.client_hello.sni
            logger.debug(f"TLS ClientHello received, SNI: {sni}")
        except Exception as e:
            logger.warning(f"Error extracting SNI: {e}")

    def tls_start_client(self, data):
        """开始客户端 TLS 握手时调用"""
        logger.debug(f"TLS start client: {data.context.client.peername}")

    def tls_start_server(self, data):
        """开始服务器 TLS 握手时调用"""
        logger.debug(f"TLS start server: {data.context.server.address}")

    @staticmethod
    def _get_flow_server_address(flow) -> tuple[Optional[str], Optional[int]]:
        server_conn = getattr(flow, "server_conn", None)
        if not server_conn:
            return None, None

        for attr in ("address", "peername"):
            value = getattr(server_conn, attr, None)
            if isinstance(value, tuple) and len(value) >= 2:
                host = value[0]
                port = value[1]
                if isinstance(host, str) and isinstance(port, int):
                    return host, port

        return None, None

    @staticmethod
    def _ensure_flow_metadata(flow) -> Dict[str, Any]:
        metadata = getattr(flow, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            flow.metadata = metadata
        return metadata

    @staticmethod
    def _looks_like_http_request(payload: bytes) -> bool:
        return payload.startswith((
            b"GET ",
            b"POST ",
            b"PUT ",
            b"DELETE ",
            b"HEAD ",
            b"OPTIONS ",
            b"PATCH ",
            b"CONNECT ",
            b"PRI * HTTP/2.0",
        ))

    def _extract_http_url_from_raw_payload(self, payload: bytes, dst_port: int) -> Optional[str]:
        if not payload or not self._looks_like_http_request(payload):
            return None

        try:
            first_line_end = payload.find(b"\r\n")
            if first_line_end == -1:
                first_line_end = payload.find(b"\n")
            if first_line_end == -1:
                return None

            first_line = payload[:first_line_end].decode("ascii", errors="ignore")
            parts = first_line.split(" ")
            if len(parts) < 2:
                return None

            method = parts[0].upper()
            path = parts[1]
            if method == "CONNECT":
                return f"https://{path}/"

            headers_start = first_line_end + 2
            headers_section = payload[headers_start:].decode("ascii", errors="ignore")

            host = None
            for line in headers_section.split("\r\n"):
                if line.lower().startswith("host:"):
                    host = line[5:].strip()
                    break
                if line == "":
                    break

            if not host or not path:
                return None

            if path.startswith(("http://", "https://")):
                return path

            scheme = "https" if dst_port == 443 else "http"
            return f"{scheme}://{host}{path}"
        except Exception:
            logger.debug("Failed to parse raw HTTP payload", exc_info=True)
            return None

    def _handle_raw_tcp_http_request(self, url: str) -> None:
        self.sniffer.record_request(url)
        logger.info("[TCP] Parsed raw HTTP request: %s", url[:160])

        if self._video_url_extractor.is_video_url(url) or PlatformDetector.is_channels_video_url(url):
            video = self.sniffer.add_video_from_url(url)
            if video:
                logger.info("[TCP] Added video from raw HTTP request: %s", url[:160])

    def _handle_raw_tcp_tls_client_hello(self, flow, payload: bytes) -> bool:
        tls_info = self._ech_handler.parse_tls_client_hello(payload)
        dst_ip, dst_port = self._get_flow_server_address(flow)
        if not tls_info or not dst_ip or not dst_port:
            return False

        host = tls_info.sni or dst_ip
        classification = "tcp_tls_sni"
        if tls_info.has_ech and not tls_info.sni:
            classification = "tcp_tls_ech"
        elif not tls_info.sni:
            classification = "tcp_tls_no_sni"

        self.sniffer.record_relevant_response(
            f"https://{host}/",
            "application/tls",
            None,
            classification,
        )
        logger.info(
            "[TCP] Parsed raw TLS ClientHello: sni=%s has_ech=%s dest=%s:%s",
            tls_info.sni or "<none>",
            tls_info.has_ech,
            dst_ip,
            dst_port,
        )

        if not tls_info.sni and self._ech_handler.is_video_server_ip(dst_ip):
            self.sniffer.record_relevant_response(
                f"https://{dst_ip}/",
                "application/tls",
                None,
                "tcp_tls_video_ip",
            )
            logger.info(
                "[TCP] Raw TLS without SNI matched Tencent video IP: dest=%s:%s",
                dst_ip,
                dst_port,
            )

        return True

    def _should_flag_midstream_tcp(self, payload: bytes, dst_ip: Optional[str], dst_port: Optional[int]) -> bool:
        if not payload or not dst_ip or not dst_port:
            return False
        if len(payload) < 8:
            return False
        if self._looks_like_http_request(payload):
            return False
        if payload[:1] == b"\x16":
            return False
        if dst_port not in (80, 443) and not self._ech_handler.is_video_server_ip(dst_ip):
            return False
        return payload[:1] in (b"\x14", b"\x15", b"\x17") or dst_port in (80, 443)

    def tcp_message(self, flow) -> None:
        try:
            messages = getattr(flow, "messages", None)
            if not messages:
                return

            message = messages[-1]
            from_client = getattr(message, "from_client", False)

            payload = bytes(getattr(message, "content", b"") or b"")
            if not payload:
                return

            dst_ip, dst_port = self._get_flow_server_address(flow)
            if not dst_ip or not dst_port:
                return

            client_port = self._get_client_port_from_flow(flow)
            process_name, process_pid = self._lookup_process_info_by_client_port(client_port)
            self.sniffer.note_renderer_process_activity(process_name, process_pid)
            process_suffix = f" process={process_name}" if process_name else ""
            metadata = self._ensure_flow_metadata(flow)
            tcp_state = metadata.setdefault(
                "vidflow_tcp_state",
                {
                    "client_prefix": b"",
                    "server_prefix": b"",
                    "logged_http": False,
                    "logged_tls": False,
                    "logged_midstream": False,
                    "logged_server_binary_hit": False,
                    "logged_server_binary_probe": False,
                },
            )
            prefix_key = "client_prefix" if from_client else "server_prefix"
            tcp_state[prefix_key] = (tcp_state[prefix_key] + payload)[:16384]
            prefix = tcp_state[prefix_key]

            if not from_client:
                source_url = f"http://{dst_ip}:{dst_port}/__vidflow_raw_tcp__"
                hit, probe_detail = self._probe_binary_metadata_response(source_url, prefix)
                if hit and not tcp_state["logged_server_binary_hit"]:
                    tcp_state["logged_server_binary_hit"] = True
                    self.sniffer.record_relevant_response(
                        f"tcp://{dst_ip}:{dst_port}/",
                        "application/octet-stream",
                        None,
                        "tcp_server_binary_hit",
                        probe_detail,
                    )
                    logger.info(
                        "[TCP] Cached metadata from raw server TCP stream: dest=%s:%s%s",
                        dst_ip,
                        dst_port,
                        process_suffix,
                    )
                    return

                if not hit and len(prefix) >= 256 and not tcp_state["logged_server_binary_probe"]:
                    tcp_state["logged_server_binary_probe"] = True
                    self.sniffer.record_relevant_response(
                        f"tcp://{dst_ip}:{dst_port}/",
                        "application/octet-stream",
                        None,
                        "tcp_server_binary_probe",
                        probe_detail,
                    )
                    logger.info(
                        "[TCP] Raw server TCP stream produced no metadata yet: dest=%s:%s prefix=%s detail=%s%s",
                        dst_ip,
                        dst_port,
                        prefix[:12].hex(),
                        probe_detail or "n/a",
                        process_suffix,
                    )

                if not tcp_state["logged_midstream"] and self._should_flag_midstream_tcp(prefix, dst_ip, dst_port):
                    tcp_state["logged_midstream"] = True
                    self.sniffer.record_relevant_response(
                        f"tcp://{dst_ip}:{dst_port}/",
                        "application/octet-stream",
                        None,
                        "tcp_midstream_or_non_tls",
                    )
                    logger.info(
                        "[TCP] Raw TCP flow does not start with HTTP or TLS ClientHello; likely attached mid-stream: "
                        "dest=%s:%s prefix=%s%s",
                        dst_ip,
                        dst_port,
                        prefix[:12].hex(),
                        process_suffix,
                    )
                return

            if not tcp_state["logged_http"]:
                raw_url = self._extract_http_url_from_raw_payload(prefix, dst_port)
                if raw_url:
                    tcp_state["logged_http"] = True
                    self._handle_raw_tcp_http_request(raw_url)
                    return

            if not tcp_state["logged_tls"] and self._handle_raw_tcp_tls_client_hello(flow, prefix):
                tcp_state["logged_tls"] = True
                return

            if not tcp_state["logged_midstream"] and self._should_flag_midstream_tcp(prefix, dst_ip, dst_port):
                tcp_state["logged_midstream"] = True
                self.sniffer.record_relevant_response(
                    f"tcp://{dst_ip}:{dst_port}/",
                    "application/octet-stream",
                    None,
                    "tcp_midstream_or_non_tls",
                )
                logger.info(
                    "[TCP] Raw TCP flow does not start with HTTP or TLS ClientHello; likely attached mid-stream: "
                    "dest=%s:%s prefix=%s%s",
                    dst_ip,
                    dst_port,
                    prefix[:12].hex(),
                    process_suffix,
                )
        except Exception:
            logger.debug("Failed to inspect raw TCP message", exc_info=True)

    def error(self, flow):
        """发生错误时调用"""
        self.error_count += 1
        err_msg = str(flow.error) if flow.error else "unknown"
        # 常见的连接关闭错误降为 debug，避免日志噪声
        if any(p in err_msg for p in ["peer closed", "connection cancelled", "timed out", "reset by peer"]):
            logger.debug(f"Flow error #{self.error_count}: {err_msg}")
        else:
            logger.error(f"Flow error #{self.error_count}: {err_msg}")

    def _try_extract_api_metadata(self, flow) -> None:
        """尝试从 API 响应中提取视频元数据

        Args:
            flow: mitmproxy flow 对象
        """
        try:
            url = flow.request.pretty_url
            content_type = flow.response.headers.get("Content-Type", "")

            # 调试日志
            content_type_lower = content_type.lower()
            response_text = self._get_flow_response_text(flow)
            response_bytes = self._get_flow_response_bytes(flow)
            status_code = getattr(flow.response, "status_code", None)
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            is_mmtls = "/mmtls/" in ((parsed_url.path or "").lower())
            path_lower = (parsed_url.path or "").lower()
            is_wechat_api = any(d in domain for d in [
                'weixin.qq.com',
                'wechat.com',
                'qq.com',
                'qpic.cn'
            ])
            if not is_wechat_api and not is_mmtls:
                logger.debug(f"[META] Not a WeChat API: {domain}")
                return

            is_textual = self._is_textual_metadata_response(url, content_type_lower, response_text)
            if is_mmtls or any(
                host in domain
                for host in [
                    "channels.weixin.qq.com",
                    "wxa.wxs.qq.com",
                    "servicewechat.com",
                    "liteapp.weixin.qq.com",
                    "mp.weixin.qq.com",
                    "extshort.weixin.qq.com",
                    "res.wx.qq.com",
                ]
            ):
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    status_code,
                    "mmtls" if is_mmtls else ("textual" if is_textual else "non_textual"),
                )
                logger.info(
                    "[META] Channels response observed: status=%s type=%s textual=%s url=%s",
                    status_code,
                    content_type or "<empty>",
                    is_textual,
                    url[:120],
                )
                if (
                    self._is_supported_channels_inject_host(domain)
                    and self._is_supported_channels_page_request(domain, path_lower)
                    and path_lower not in {CHANNELS_INJECT_PROXY_PATH, CHANNELS_INJECT_SCRIPT_PATH}
                    and not self.sniffer.has_channels_page_injection()
                ):
                    self._schedule_page_metadata_prefetch(flow, url)
                    self.sniffer.maybe_recycle_wechat_renderer(
                        "channels_web_activity_without_injection",
                        url,
                    )

            if is_mmtls:
                hit, probe_detail = self._probe_binary_metadata_response(url, response_bytes)
                self.sniffer.record_relevant_response(
                    url,
                    content_type,
                    status_code,
                    "mmtls_binary_hit" if hit else "mmtls_binary_miss",
                    probe_detail,
                )
                if hit:
                    return
                logger.info(
                    "[MMTLS] Binary metadata miss: detail=%s url=%s",
                    probe_detail or "unknown",
                    url[:120],
                )

            if not is_textual:
                logger.debug(f"[META] Skipping non-text response")
                return

            if not response_text.strip():
                return
            logger.debug(f"[META] Checking URL: {url[:80]}, Content-Type: {content_type}")

            # 跳过 JS/CSS 等静态资源文件——这些文件可能包含
            # encfilekey、finder.video.qq.com 等字符串（应用代码引用），
            # 会被误识别为视频元数据
            _STATIC_ASSET_CONTENT_TYPES = ("javascript", "css", "wasm", "font")
            if any(t in content_type_lower for t in _STATIC_ASSET_CONTENT_TYPES):
                return

            # 非 JSON 的文本响应（如 HTML）也尝试提取嵌入的视频元数据
            if "json" not in content_type_lower:
                self._cache_text_response_metadata(url, response_text)
                return

            logger.info(f"[META] Found JSON response: {url[:80]}")

            # 检查是否是微信相关的 API
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            is_wechat_api = any(d in domain for d in [
                'weixin.qq.com',
                'wechat.com',
                'qq.com',
                'qpic.cn'
            ])

            if not is_wechat_api:
                logger.debug(f"[META] Not a WeChat API: {domain}")
                return

            if not self._is_textual_metadata_response(url, content_type_lower, response_text):
                logger.debug(f"[META] Skipping non-text response")
                return

            if not response_text.strip():
                return

            logger.info(f"[META] WeChat API detected: {domain}")
            self._cache_text_response_metadata(url, response_text)

            # 尝试解析 JSON 响应
            try:
                import json
                data = json.loads(response_text)

                # 尝试从 JSON 中提取多个视频的元数据（批量 API 响应）
                feed_items = self._extract_feed_items_from_json(data)
                if feed_items:
                    cached_count = 0
                    for feed_item in feed_items:
                        item_metadata = self._parse_wechat_api_response(feed_item)
                        if not item_metadata or not (item_metadata.title or item_metadata.thumbnail or item_metadata.filesize):
                            continue
                        item_cache_keys = self._extract_cache_keys_from_json_item(feed_item)
                        if item_cache_keys:
                            self.cache_external_metadata(item_metadata, item_cache_keys)
                            cached_count += 1
                    if cached_count > 0:
                        logger.info(f"批量缓存 API 元数据: {cached_count} 个视频")
                else:
                    # 回退：整体提取单个元数据（非列表型 API 响应）
                    metadata = self._parse_wechat_api_response(data)
                    if metadata and (metadata.title or metadata.thumbnail or metadata.filesize):
                        cache_keys = []
                        query_params = parse_qs(parsed_url.query)
                        for key_param in [
                            'encfilekey', 'm', 'taskid', 'taskId',
                            'objectid', 'feedid', 'objectId', 'feedId',
                            'filekey', 'videoId', 'video_id', 'mediaId', 'mediaid',
                        ]:
                            if key_param in query_params:
                                cache_keys.append(query_params[key_param][0])
                        json_key = self._extract_video_key_from_json(data)
                        if json_key and json_key not in cache_keys:
                            cache_keys.append(json_key)
                        if cache_keys:
                            video_id = self._extract_video_id_from_json(data)
                            if video_id:
                                cache_keys.insert(0, video_id)
                            self.cache_external_metadata(metadata, cache_keys)
                            logger.info(f"缓存 API 元数据: title={metadata.title}, keys={len(cache_keys)}")

            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.debug(f"Error parsing API response: {e}")

        except Exception as e:
            logger.debug(f"Error extracting API metadata: {e}")

    @staticmethod
    def _looks_like_text_payload(response_text: str) -> bool:
        if not response_text:
            return False

        sample = response_text[:4096]
        printable = sum(1 for ch in sample if ch.isprintable() or ch in "\r\n\t")
        ratio = printable / max(len(sample), 1)
        if ratio < 0.85:
            return False

        lower_sample = sample.lower()
        return any(
            token in lower_sample
            for token in [
                "<html",
                "<!doctype html",
                "__initial_state__",
                "window.__",
                '"title"',
                '"thumburl"',
                '"decodekey"',
                "encfilekey",
                "taskid",
            ]
        )

    @classmethod
    def _looks_like_html_document(cls, url: str, content_type: str, response_text: str) -> bool:
        try:
            parsed_url = urlparse(url)
            path_lower = (parsed_url.path or "").lower()
        except Exception:
            path_lower = ""

        content_type_lower = (content_type or "").lower()
        if any(token in content_type_lower for token in ["text/html", "application/xhtml+xml"]):
            return True

        if path_lower.endswith((
            ".js", ".mjs", ".css", ".json", ".jpg", ".jpeg", ".png", ".webp",
            ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".map",
        )):
            return False

        lower_text = (response_text or "")[:8192].lower()
        if "<html" in lower_text or "<!doctype html" in lower_text:
            return True

        return False

    @classmethod
    def _is_textual_metadata_response(cls, url: str, content_type: str, response_text: str = "") -> bool:
        try:
            parsed_url = urlparse(url)
            path_lower = (parsed_url.path or "").lower()
        except Exception:
            path_lower = ""

        if "/mmtls/" in path_lower:
            return False

        if any(token in (content_type or "") for token in [
            "json",
            "javascript",
            "ecmascript",
            "text/",
            "html",
            "xml",
        ]):
            return True

        if cls._looks_like_html_document(url, content_type, response_text):
            return True

        if cls._looks_like_text_payload(response_text):
            return True

        return path_lower.endswith((".js", ".json", ".html", ".htm", ".txt"))

    @staticmethod
    def _get_flow_response_text(flow) -> str:
        try:
            if hasattr(flow.response, "get_text"):
                return flow.response.get_text(strict=False) or ""
        except Exception:
            logger.debug("[META] Failed to read flow text via get_text", exc_info=True)

        try:
            content = getattr(flow.response, "content", b"") or b""
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="ignore")
            return str(content)
        except Exception:
            logger.debug("[META] Failed to decode response body", exc_info=True)
            return ""

    @staticmethod
    def _get_flow_response_bytes(flow) -> bytes:
        try:
            content = getattr(flow.response, "content", b"") or b""
            if isinstance(content, bytes):
                return content
            if isinstance(content, bytearray):
                return bytes(content)
            if isinstance(content, str):
                return content.encode("utf-8", errors="ignore")
        except Exception:
            logger.debug("[META] Failed to read response body bytes", exc_info=True)
        return b""

    @staticmethod
    def _normalize_text_metadata_payload(text: str) -> str:
        normalized = (text or "")
        normalized = normalized.replace("\\u0026", "&").replace("\\/", "/")
        return unescape(normalized)

    @staticmethod
    def _extract_context_string(context: str, field_names: List[str], max_length: int = 200) -> Optional[str]:
        joined = "|".join(re.escape(name) for name in field_names)
        key_prefix = r'(?<![A-Za-z0-9_])'
        key_suffix = r'(?![A-Za-z0-9_])'
        patterns = [
            rf'{key_prefix}["\'](?:{joined})["\']{key_suffix}\s*[:=]\s*["\']([^"\n\r]{{1,{max_length}}})["\']',
            rf'{key_prefix}(?:{joined}){key_suffix}\s*[:=]\s*["\']([^"\n\r]{{1,{max_length}}})["\']',
            rf'{key_prefix}["\']?(?:{joined})["\']?{key_suffix}\s*[:=]\s*([^,\]\}}\r\n]{{1,{max_length}}})',
        ]
        for pattern in patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip().strip('"\'')
            if value:
                return value
        return None

    @staticmethod
    def _extract_context_int(context: str, field_names: List[str]) -> Optional[int]:
        joined = "|".join(re.escape(name) for name in field_names)
        key_prefix = r'(?<![A-Za-z0-9_])'
        key_suffix = r'(?![A-Za-z0-9_])'
        patterns = [
            rf'{key_prefix}["\'](?:{joined})["\']{key_suffix}\s*[:=]\s*["\']?(\d{{1,12}})["\']?',
            rf'{key_prefix}(?:{joined}){key_suffix}\s*[:=]\s*["\']?(\d{{1,12}})["\']?',
        ]
        for pattern in patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if not match:
                continue
            try:
                return int(match.group(1))
            except (TypeError, ValueError):
                continue
        return None

    def _extract_text_response_candidates(self, source_url: str, response_text: str) -> List[Dict[str, Any]]:
        normalized_text = self._normalize_text_metadata_payload(response_text)
        if not normalized_text:
            return []

        source_url_lower = (source_url or "").lower()
        source_is_channels_page = "channels.weixin.qq.com" in source_url_lower
        source_is_channels_video = PlatformDetector.is_channels_video_url(source_url)
        try:
            parsed_source_url = urlparse(source_url)
            source_path_lower = (parsed_source_url.path or "").lower()
        except Exception:
            source_path_lower = ""
        source_is_static_asset = source_path_lower.endswith((".js", ".mjs", ".css"))
        strong_markers = sum(
            marker in normalized_text.lower()
            for marker in (
                "finder.video.qq.com",
                "findervideodownload.video.qq.com",
                "stodownload",
                "encfilekey",
                "taskid",
                "feedid",
                "objectid",
                "decodekey",
                "decryptkey",
                "decryptionkey",
                "seedvalue",
                "videokey",
                "mediakey",
            )
        )
        if strong_markers == 0 and not source_is_channels_video:
            return []

        url_pattern = re.compile(
            r'(?:(?:https?:)?//)?(?:finder\.video\.qq\.com|findervideodownload\.video\.qq\.com|(?:[\w-]+\.)?tc\.qq\.com)/[^"\'\\\s<>]+',
            re.IGNORECASE,
        )
        thumb_pattern = re.compile(
            r'(?:(?:https?:)?//)?(?:[^"\'\\\s<>]*(?:qpic|wx\.qlogo|wx\.qpic|qlogo)\.[^"\'\\\s<>]+|res\.wx\.qq\.com/[^"\'\\\s<>]+)',
            re.IGNORECASE,
        )
        url_fields = [
            "url", "videoUrl", "video_url", "mediaUrl", "media_url",
            "playUrl", "play_url", "downloadUrl", "download_url",
            "videoPlayUrl", "video_play_url", "src", "videoSrc", "video_src",
        ]
        title_fields = [
            "title", "desc", "description", "feedDesc", "feedTitle",
            "videoTitle", "video_title", "content", "contentDesc", "caption",
            "shareTitle", "share_title", "shareDesc", "share_desc",
            "finderTitle", "finder_title", "finderDesc", "finder_desc",
            "descriptionText", "contentText",
            "headline", "objectDesc.description", "objectDesc.desc",
            "objectDesc.title", "objectDesc.content", "objectDesc.contentDesc",
            "media.title", "media.description", "media.desc",
        ]
        thumbnail_fields = [
            "thumbUrl", "thumb_url", "thumb", "cover", "coverUrl", "cover_url",
            "coverImage", "cover_image", "coverImg", "cover_img",
            "coverImgUrl", "cover_img_url", "headUrl", "head_url", "thumburl",
            "poster", "posterUrl", "poster_url", "imageUrl", "image_url",
        ]
        decode_key_fields = [
            "decodeKey", "decode_key", "decodeKey64", "decode_key64",
            "decryptKey", "decrypt_key", "decryptionKey", "decryption_key",
            "decryptSeed", "decrypt_seed", "seed", "seedValue", "seed_value",
            "mediaKey", "media_key", "videoKey", "video_key", "dk",
        ]
        duration_fields = ["duration", "videoDuration", "video_duration", "playDuration", "play_duration", "videoTime", "video_time"]
        width_fields = ["width", "videoWidth", "video_width"]
        height_fields = ["height", "videoHeight", "video_height"]
        filesize_fields = ["fileSize", "file_size", "videoSize", "video_size", "size", "filesize"]
        cache_key_fields = [
            "encfilekey", "m", "taskid", "taskId",
            "objectid", "feedid", "objectId", "feedId",
            "filekey", "videoId", "video_id", "mediaId", "mediaid",
        ]

        candidates: List[Dict[str, Any]] = []
        seen_urls = set()
        seen_cache_signatures = set()

        def normalize_embedded_url(value: Optional[str]) -> Optional[str]:
            if not value:
                return None

            candidate = self._normalize_text_metadata_payload(str(value)).strip().strip('"\'')
            if candidate.startswith("//"):
                return f"https:{candidate}"
            if candidate.startswith(("http://", "https://")):
                return candidate
            if re.match(
                r'^(?:finder\.video\.qq\.com|findervideodownload\.video\.qq\.com|(?:[\w-]+\.)?tc\.qq\.com)/',
                candidate,
                re.IGNORECASE,
            ):
                return f"https://{candidate.lstrip('/')}"
            if re.match(
                r'^(?:res\.wx\.qq\.com|[^/]*(?:qpic|wx\.qlogo|wx\.qpic|qlogo)\.[^/]+)/',
                candidate,
                re.IGNORECASE,
            ):
                return f"https://{candidate.lstrip('/')}"
            if candidate.startswith("/") and ("stodownload" in candidate.lower() or "encfilekey=" in candidate.lower()):
                return f"https://finder.video.qq.com{candidate}"
            if re.match(r'^(?:\d+/){2}stodownload(?:\?|$)', candidate, re.IGNORECASE):
                return f"https://finder.video.qq.com/{candidate.lstrip('/')}"
            return None

        def build_url_from_context(context: str) -> Optional[str]:
            direct_url = normalize_embedded_url(
                self._extract_context_string(context, url_fields, max_length=2000)
            )
            if direct_url:
                normalized_direct_url = ChannelsDownloader._normalize_video_url(direct_url)
                if normalized_direct_url:
                    return normalized_direct_url

            embedded_match = url_pattern.search(context)
            if not embedded_match:
                return None

            embedded_url = normalize_embedded_url(embedded_match.group(0).rstrip('"\';,)}]>'))
            if not embedded_url:
                return None

            return ChannelsDownloader._normalize_video_url(embedded_url)

        def build_metadata_from_context(context: str) -> Optional[VideoMetadata]:
            title = self.sniffer._sanitize_video_title(
                self._extract_context_string(
                    context,
                    title_fields,
                    max_length=160,
                )
            )
            if not title:
                object_nonce_title = self._extract_context_string(
                    context,
                    ["objectNonceId"],
                    max_length=64,
                )
                if object_nonce_title and not self.sniffer._looks_like_placeholder_nonce(object_nonce_title):
                    title = self.sniffer._sanitize_video_title(object_nonce_title)
            thumbnail = self.sniffer._extract_thumbnail_url(
                self._extract_context_string(context, thumbnail_fields, max_length=1024)
            )
            if not thumbnail:
                thumbnail_match = thumb_pattern.search(context)
                thumbnail = self.sniffer._extract_thumbnail_url(thumbnail_match.group(0) if thumbnail_match else None)
            decode_key = self.sniffer._normalize_decode_key(
                self._extract_context_string(
                    context,
                    decode_key_fields,
                    max_length=32,
                )
            )
            if not decode_key:
                numeric_decode_key = self._extract_context_int(
                    context,
                    decode_key_fields,
                )
                if numeric_decode_key is not None:
                    decode_key = str(numeric_decode_key)
            duration = self._extract_context_int(context, duration_fields)
            width = self._extract_context_int(context, width_fields)
            height = self._extract_context_int(context, height_fields)
            filesize = self._extract_context_int(context, filesize_fields)

            if source_is_static_asset and thumbnail and not any([title, decode_key, duration, width, height, filesize]):
                return None

            has_rich_metadata = any([thumbnail, decode_key, duration, width, height, filesize])
            if not any([title, thumbnail, decode_key, duration, width, height, filesize]):
                return None
            if not has_rich_metadata and not build_url_from_context(context):
                return None

            return VideoMetadata(
                title=title,
                duration=duration,
                resolution=f"{width}x{height}" if width and height else None,
                filesize=filesize,
                thumbnail=thumbnail,
                width=width,
                height=height,
                decode_key=decode_key,
            )

        def collect_cache_keys(context: str, fallback_url: Optional[str] = None) -> List[str]:
            keys: List[str] = []
            cache_key_pattern = "|".join(re.escape(name) for name in cache_key_fields)
            key_patterns = [
                re.compile(
                    rf'["\']?({cache_key_pattern})["\']?\s*[:=]\s*["\']?([^"\'\\\s<>,\]\}}]{{1,256}})["\']?',
                    re.IGNORECASE,
                ),
                re.compile(
                    rf'(?:[?&])({cache_key_pattern})=([^&"\'\\\s<>]{{1,256}})',
                    re.IGNORECASE,
                ),
            ]

            for pattern in key_patterns:
                for match in pattern.finditer(context):
                    value = match.group(2).strip()
                    if value and value not in keys:
                        keys.append(value)

            if fallback_url:
                for cache_key in self.sniffer._build_metadata_cache_keys(fallback_url):
                    if cache_key not in keys:
                        keys.append(cache_key)

            for cache_key in self.sniffer._build_metadata_cache_keys(source_url):
                if cache_key not in keys:
                    keys.append(cache_key)

            return self.sniffer._normalize_metadata_cache_keys(keys)

        for match in url_pattern.finditer(normalized_text):
            raw_url = normalize_embedded_url(match.group(0).rstrip('"\';,)}]>'))
            normalized_url = ChannelsDownloader._normalize_video_url(raw_url)
            if (
                not normalized_url
                or not PlatformDetector.is_channels_video_url(normalized_url)
                or normalized_url in seen_urls
            ):
                continue

            seen_urls.add(normalized_url)
            context_start = max(0, match.start() - 8000)
            context_end = min(len(normalized_text), match.end() + 8000)
            context = normalized_text[context_start:context_end]
            metadata = build_metadata_from_context(context)
            if not metadata:
                continue
            cache_keys = collect_cache_keys(context, normalized_url)

            if not cache_keys:
                continue

            if not metadata.decode_key and not normalized_url and not source_is_channels_video:
                continue

            signature = tuple(cache_keys)
            if signature in seen_cache_signatures:
                continue
            seen_cache_signatures.add(signature)

            candidates.append({
                "url": normalized_url,
                "metadata": metadata,
                "cache_keys": cache_keys,
            })

        cache_key_pattern = "|".join(re.escape(name) for name in cache_key_fields)
        key_anchor_pattern = re.compile(
            rf'["\']?({cache_key_pattern})["\']?\s*[:=]\s*["\']?([^"\'\\\s<>,\]\}}]{{1,256}})["\']?',
            re.IGNORECASE,
        )
        for match in key_anchor_pattern.finditer(normalized_text):
            context_start = max(0, match.start() - 8000)
            context_end = min(len(normalized_text), match.end() + 8000)
            context = normalized_text[context_start:context_end]
            metadata = build_metadata_from_context(context)
            if not metadata:
                continue

            cache_keys = collect_cache_keys(context)
            if not cache_keys:
                continue

            candidate_url = build_url_from_context(context)
            if not candidate_url and source_is_channels_video:
                candidate_url = ChannelsDownloader._normalize_video_url(source_url)

            if (
                not metadata.decode_key
                and not candidate_url
                and not source_is_channels_video
                and not source_is_channels_page
            ):
                continue

            signature = tuple(cache_keys)
            if signature in seen_cache_signatures:
                continue
            seen_cache_signatures.add(signature)

            candidates.append({
                "url": candidate_url,
                "metadata": metadata,
                "cache_keys": cache_keys,
            })

        return candidates

    @classmethod
    def _build_binary_probe_texts(cls, response_bytes: bytes) -> List[str]:
        probe_bytes = (response_bytes or b"")[:512 * 1024]
        if not probe_bytes:
            return []

        probe_texts: List[str] = []
        seen = set()

        def add_candidate(text: str) -> None:
            normalized = cls._normalize_text_metadata_payload(text).strip()
            if len(normalized) < 24:
                return
            signature = normalized[:4096]
            if signature in seen:
                return
            seen.add(signature)
            probe_texts.append(normalized)

        try:
            add_candidate(probe_bytes.decode("utf-8", errors="ignore"))
        except Exception:
            logger.debug("[MMTLS] Failed UTF-8 probe decode", exc_info=True)

        try:
            ascii_segments = re.findall(rb"[\x20-\x7e]{12,}", probe_bytes)
            if ascii_segments:
                add_candidate(
                    "\n".join(
                        segment.decode("ascii", errors="ignore")
                        for segment in ascii_segments[:800]
                    )
                )
        except Exception:
            logger.debug("[MMTLS] Failed ASCII segment extraction", exc_info=True)

        if probe_bytes.count(b"\x00") * 4 >= len(probe_bytes):
            try:
                add_candidate(probe_bytes.decode("utf-16-le", errors="ignore"))
            except Exception:
                logger.debug("[MMTLS] Failed UTF-16LE probe decode", exc_info=True)

        gzip_offset = probe_bytes.find(b"\x1f\x8b\x08")
        if 0 <= gzip_offset < min(len(probe_bytes), 65536):
            try:
                add_candidate(gzip.decompress(probe_bytes[gzip_offset:]).decode("utf-8", errors="ignore"))
            except Exception:
                logger.debug("[MMTLS] Failed gzip probe decode", exc_info=True)

        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                add_candidate(zlib.decompress(probe_bytes, wbits).decode("utf-8", errors="ignore"))
            except Exception:
                continue

        zlib_headers = {b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda"}
        zlib_offsets: List[int] = []
        search_limit = min(max(len(probe_bytes) - 1, 0), 128 * 1024)
        for index in range(search_limit):
            if probe_bytes[index:index + 2] not in zlib_headers:
                continue
            zlib_offsets.append(index)
            if len(zlib_offsets) >= 24:
                break

        for offset in zlib_offsets:
            try:
                add_candidate(
                    zlib.decompress(probe_bytes[offset:], zlib.MAX_WBITS).decode("utf-8", errors="ignore")
                )
            except Exception:
                continue

        if brotli is not None:
            brotli_hits = 0
            max_brotli_offset = min(len(probe_bytes), 64)
            max_brotli_trim = min(32, max(len(probe_bytes) - 1, 0))
            for offset in range(max_brotli_offset):
                decoded = False
                for trim in range(max_brotli_trim + 1):
                    end = len(probe_bytes) - trim
                    if end - offset < 8:
                        break

                    try:
                        add_candidate(
                            brotli.decompress(probe_bytes[offset:end]).decode("utf-8", errors="ignore")
                        )
                        brotli_hits += 1
                        decoded = True
                        break
                    except Exception:
                        continue

                if brotli_hits >= 4:
                    break
                if decoded:
                    continue

        return probe_texts

    def _probe_binary_metadata_response(self, source_url: str, response_bytes: bytes) -> tuple[bool, Optional[str]]:
        probe_texts = self._build_binary_probe_texts(response_bytes)
        if not probe_texts:
            return False, "no_decodable_text"

        markers = set()
        for probe_text in probe_texts:
            lowered = probe_text.lower()
            for marker in (
                "finder.video.qq.com",
                "encfilekey",
                "decodekey",
                "decryptkey",
                "thumburl",
                "thumb_url",
                "title",
            ):
                if marker in lowered:
                    markers.add(marker)

            candidates = self._extract_text_response_candidates(source_url, probe_text)
            if not candidates:
                continue

            for candidate in candidates:
                self.cache_external_metadata(candidate["metadata"], candidate["cache_keys"])
                metadata = candidate["metadata"]
                candidate_url = candidate["url"]
                if candidate_url and PlatformDetector.is_channels_video_url(candidate_url):
                    self.sniffer.ingest_injected_video(
                        url=candidate_url,
                        title=metadata.title,
                        thumbnail=metadata.thumbnail,
                        duration=metadata.duration,
                        width=metadata.width,
                        height=metadata.height,
                        filesize=metadata.filesize,
                        decode_key=metadata.decode_key,
                    )
                logger.info(
                    "[MMTLS] Cached metadata from binary response: title=%s thumbnail=%s decodeKey=%s cache_keys=%s url=%s",
                    metadata.title,
                    "yes" if metadata.thumbnail else "no",
                    "yes" if metadata.decode_key else "no",
                    len(candidate["cache_keys"]),
                    (candidate_url or source_url)[:120],
                )
            return True, f"candidates={len(candidates)}"

        # 尝试在原始二进制中扫描 protobuf 编码的 URL 和 decodeKey
        # 即使文本探测失败，MMTLS 包体内可能有 protobuf length-delimited 字段
        # 包含 finder.video.qq.com URL 或 decodeKey（uint64 varint）
        proto_hit, proto_detail = self._probe_protobuf_fields(source_url, response_bytes)
        if proto_hit:
            return True, f"protobuf:{proto_detail}"

        if markers:
            logger.info(
                "[MMTLS] Binary response contained channels markers but no complete metadata: markers=%s url=%s",
                ",".join(sorted(markers)),
                source_url[:120],
            )
            return False, f"markers={','.join(sorted(markers))}"

        return False, "no_channels_markers"

    def _probe_protobuf_fields(self, source_url: str, response_bytes: bytes) -> tuple[bool, Optional[str]]:
        """尝试在二进制数据中扫描 protobuf 编码的视频元数据

        MMTLS 数据可能包含嵌套的 protobuf 消息，其中：
        - finder.video.qq.com URL 作为 length-delimited string 字段
        - decodeKey 作为 varint (uint64) 字段
        - encfilekey 作为 length-delimited string 字段

        即使无法完整解析 protobuf 结构，也可以通过模式匹配提取有用信息。
        """
        if not response_bytes or len(response_bytes) < 64:
            return False, None

        data = response_bytes[:512 * 1024]

        # 扫描嵌入的 URL（finder.video.qq.com 或 stodownload）
        url_pattern = re.compile(
            rb'(https?://(?:finder\.video\.qq\.com|findervideodownload\.video\.qq\.com)/[^\x00-\x1f\x7f-\x9f]{20,600})'
        )
        urls_found = url_pattern.findall(data)

        if not urls_found:
            return False, None

        logger.info(
            "[MMTLS/Proto] 在二进制响应中发现 %d 个嵌入 URL: %s",
            len(urls_found),
            source_url[:120],
        )

        # 尝试提取 decodeKey：扫描附近区域中可能的 uint64 数字字符串
        # 微信的 decodeKey 通常是 8-20 位纯数字（uint64），可能以 ASCII 或 protobuf varint 编码
        decode_key = None

        # 方法 1：ASCII 数字字符串模式（"decodeKey":"1234567890" 或类似）
        dk_text_pattern = re.compile(
            rb'(?:decodeKey|decode_key|decryptKey|decrypt_key|decryptSeed|seedValue|mediaKey|videoKey|dk)'
            rb'["\x00-\x20:=]{0,8}["\x00-\x20]*([1-9]\d{5,19})',
            re.IGNORECASE,
        )
        dk_matches = dk_text_pattern.findall(data)
        for dk_match in dk_matches:
            try:
                candidate = dk_match.decode("ascii", errors="ignore").strip()
                normalized = self.sniffer._normalize_decode_key(candidate)
                if normalized:
                    decode_key = normalized
                    logger.info(
                        "[MMTLS/Proto] 从二进制文本模式提取 decodeKey: %s url=%s",
                        decode_key,
                        source_url[:120],
                    )
                    break
            except Exception:
                continue

        # 方法 2：在 URL 附近扫描独立的长数字字符串（可能是 decodeKey）
        if not decode_key:
            standalone_dk_pattern = re.compile(rb'["\x02]([1-9]\d{7,19})["\x00\x10\x12\x18\x1a\x20\x22\x28\x2a\x30]')
            for url_bytes in urls_found[:3]:
                url_offset = data.find(url_bytes)
                if url_offset < 0:
                    continue
                # 搜索 URL 前后 2KB 范围
                search_start = max(0, url_offset - 2048)
                search_end = min(len(data), url_offset + len(url_bytes) + 2048)
                search_region = data[search_start:search_end]
                dk_candidates = standalone_dk_pattern.findall(search_region)
                for dk_candidate in dk_candidates:
                    try:
                        candidate_str = dk_candidate.decode("ascii", errors="ignore")
                        normalized = self.sniffer._normalize_decode_key(candidate_str)
                        if normalized:
                            decode_key = normalized
                            logger.info(
                                "[MMTLS/Proto] 从 URL 附近提取候选 decodeKey: %s url=%s",
                                decode_key,
                                source_url[:120],
                            )
                            break
                    except Exception:
                        continue
                if decode_key:
                    break

        # 提取第一个有效 URL 并创建视频记录
        for raw_url in urls_found[:5]:
            try:
                video_url = raw_url.decode("utf-8", errors="ignore")
                video_url = PlatformDetector.normalize_channels_video_url(video_url)
                if not PlatformDetector.is_channels_video_url(video_url):
                    continue

                cache_keys = self._build_metadata_cache_keys(video_url)
                metadata = VideoMetadata(decode_key=decode_key)
                self.cache_external_metadata(metadata, cache_keys)

                if decode_key:
                    self.sniffer.ingest_injected_video(
                        url=video_url,
                        decode_key=decode_key,
                    )
                    logger.info(
                        "[MMTLS/Proto] 视频+decodeKey 提取成功: dk=%s url=%s",
                        decode_key,
                        video_url[:120],
                    )
                else:
                    # 即使没有 decodeKey，也缓存 URL 的 cache_keys 供后续关联
                    self.sniffer.reconcile_cached_metadata(cache_keys)
                    logger.info(
                        "[MMTLS/Proto] 视频 URL 已缓存（无 decodeKey）: keys=%d url=%s",
                        len(cache_keys),
                        video_url[:120],
                    )

                return True, f"urls={len(urls_found)},dk={'yes' if decode_key else 'no'}"
            except Exception as e:
                logger.debug("[MMTLS/Proto] 处理嵌入 URL 失败: %s", e)
                continue

        return False, None

    def _cache_text_response_metadata(self, source_url: str, response_text: str) -> int:
        applied = 0
        for candidate in self._extract_text_response_candidates(source_url, response_text):
            self.cache_external_metadata(candidate["metadata"], candidate["cache_keys"])
            metadata = candidate["metadata"]
            logger.info(
                "Cached metadata from text response: title=%s, thumbnail=%s, decodeKey=%s, url=%s",
                metadata.title,
                "yes" if metadata.thumbnail else "no",
                "yes" if metadata.decode_key else "no",
                (candidate["url"] or source_url)[:120],
            )
            applied += 1
        return applied

    def _cache_thumbnail_from_image(self, url: str, content_type: str) -> bool:
        """Cache thumbnail URL from image responses for later video metadata lookup."""
        try:
            if not (content_type or "").lower().startswith("image/"):
                return False

            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            candidate_keys: List[str] = []
            for key_param in [
                "encfilekey", "m", "taskid", "taskId",
                "objectid", "feedid", "objectId", "feedId",
                "filekey", "videoId", "video_id", "mediaId", "mediaid",
            ]:
                value = query_params.get(key_param, [None])[0]
                if value and value not in candidate_keys:
                    candidate_keys.append(value)

            if not candidate_keys:
                return False

            video_id = PlatformDetector.extract_video_id(url)
            cache_keys = list(candidate_keys)
            if video_id:
                cache_keys.insert(0, video_id)

            with self._metadata_cache_lock:
                for cache_key in cache_keys:
                    existing = self._metadata_cache.get(cache_key)
                    if existing:
                        if not existing.thumbnail:
                            existing.thumbnail = url
                    else:
                        self._metadata_cache[cache_key] = VideoMetadata(thumbnail=url)
                    self._metadata_cache_timestamps[cache_key] = time.time()

            logger.info(f"[META] Cached thumbnail from image response for keys={len(cache_keys)}")
            self.sniffer.reconcile_cached_metadata(cache_keys)
            return True
        except Exception as e:
            logger.debug(f"Error caching thumbnail from image response: {e}")
            return False

    def _parse_wechat_api_response(self, data: Any) -> Optional[VideoMetadata]:
        """解析微信 API 响应中的视频元数据

        Args:
            data: JSON 数据

        Returns:
            VideoMetadata 对象或 None
        """
        metadata = VideoMetadata()

        # 字段映射
        field_mapping = {
            'title': ['title', 'desc', 'description', 'feedDesc', 'feedTitle', 'feed_title', 'videoTitle', 'video_title', 'content', 'contentDesc', 'caption', 'headline', 'shareTitle', 'share_title', 'shareDesc', 'share_desc', 'finderTitle', 'finder_title', 'finderDesc', 'finder_desc', 'descriptionText', 'contentText'],
            'author': ['nickname', 'nickName', 'name', 'userName', 'authorName', 'author_name'],
            'thumbnail': ['thumbUrl', 'thumb_url', 'thumb', 'cover', 'coverUrl', 'cover_url', 'coverImage', 'cover_image', 'coverImg', 'cover_img', 'headUrl', 'head_url', 'thumburl', 'coverImgUrl', 'cover_img_url', 'poster', 'posterUrl', 'poster_url', 'imageUrl', 'image_url'],
            'duration': ['duration', 'videoTime', 'video_time', 'playDuration', 'play_duration', 'videoDuration'],
            'width': ['width', 'videoWidth', 'video_width'],
            'height': ['height', 'videoHeight', 'video_height'],
            'filesize': ['size', 'fileSize', 'file_size', 'videoSize', 'video_size', 'filesize'],
            'decode_key': [
                'decodeKey', 'decode_key', 'decodeKey64', 'decode_key64',
                'decryptKey', 'decrypt_key', 'decryptionKey', 'decryption_key',
                'decryptSeed', 'decrypt_seed', 'seed', 'seedValue', 'seed_value',
                'mediaKey', 'media_key', 'videoKey', 'video_key', 'dk',
            ],
        }

        def extract_from_dict(d: dict, metadata: VideoMetadata) -> None:
            """递归从字典中提取字段"""
            for field, keys in field_mapping.items():
                if getattr(metadata, field) is None:
                    for key in keys:
                        if key in d and d[key]:
                            value = d[key]
                            if field in ['duration', 'width', 'height', 'filesize']:
                                try:
                                    value = int(value)
                                except (ValueError, TypeError):
                                    continue
                            elif field == 'title':
                                value = self.sniffer._sanitize_video_title(str(value))
                                if not value:
                                    continue
                            elif field == 'author':
                                value = str(value).strip()
                                if not value:
                                    continue
                            elif field == 'thumbnail':
                                value = self.sniffer._extract_thumbnail_url(value)
                                if not value:
                                    continue
                            elif field == 'decode_key':
                                value = self.sniffer._normalize_decode_key(value)
                                if not value:
                                    continue
                            setattr(metadata, field, value)
                            break

            # 递归处理嵌套对象
            for nested_value in d.values():
                if isinstance(nested_value, dict):
                    extract_from_dict(nested_value, metadata)
                elif isinstance(nested_value, list):
                    for item in nested_value:
                        if isinstance(item, dict):
                            extract_from_dict(item, metadata)

        if isinstance(data, dict):
            extract_from_dict(data, metadata)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    extract_from_dict(item, metadata)

        if metadata.resolution is None and metadata.width and metadata.height:
            metadata.resolution = f"{metadata.width}x{metadata.height}"

        return metadata if (
            metadata.title
            or metadata.thumbnail
            or metadata.filesize
            or metadata.decode_key
            or metadata.duration
            or metadata.resolution
        ) else None

    def _extract_feed_items_from_json(self, data: Any) -> List[dict]:
        """从 API JSON 响应中提取视频列表（feedList/objectList 等）。"""
        if not isinstance(data, dict):
            return []
        # 直接查找已知的列表键
        list_keys = [
            'feedList', 'feed_list', 'objectList', 'object_list',
            'objects', 'feeds', 'items', 'list', 'videoList', 'video_list',
        ]
        for key in list_keys:
            value = data.get(key)
            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                return value
        # 嵌套一层查找（如 data.data.feedList）
        for outer_key in ('data', 'result', 'resp', 'response'):
            inner = data.get(outer_key)
            if isinstance(inner, dict):
                for key in list_keys:
                    value = inner.get(key)
                    if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                        return value
        return []

    def _extract_cache_keys_from_json_item(self, item: dict) -> List[str]:
        """从单个 feed item 中提取可用作缓存键的标识符。"""
        cache_keys: List[str] = []
        key_fields = [
            'objectId', 'objectid', 'feedId', 'feedid',
            'objectNonceId', 'objectnonceid',
            'encfilekey', 'encFileKey',
            'taskid', 'taskId',
            'mediaId', 'mediaid', 'videoId', 'video_id',
        ]

        def _search(d: dict, depth: int = 0) -> None:
            if depth > 4:
                return
            for field in key_fields:
                value = d.get(field)
                if value and isinstance(value, (str, int)):
                    str_value = str(value).strip()
                    if str_value and str_value not in cache_keys:
                        cache_keys.append(str_value)
            for v in d.values():
                if isinstance(v, dict):
                    _search(v, depth + 1)
                elif isinstance(v, list):
                    for elem in v:
                        if isinstance(elem, dict):
                            _search(elem, depth + 1)

        _search(item)
        # 对长 encfilekey 添加截断前缀版本，用于跨清晰度模糊匹配
        for key in list(cache_keys):
            if len(key) > 40:
                prefix_key = f"pfx:{key[:36]}"
                if prefix_key not in cache_keys:
                    cache_keys.append(prefix_key)
        return cache_keys

    def _extract_video_key_from_json(self, data: Any) -> Optional[str]:
        """从 JSON 数据中提取视频密钥

        Args:
            data: JSON 数据

        Returns:
            视频密钥或 None
        """
        key_fields = ['encfilekey', 'm', 'taskid', 'taskId', 'filekey', 'videoId', 'video_id', 'mediaId', 'mediaid', 'objectId', 'feedId', 'objectid', 'feedid']

        def search_dict(d: dict) -> Optional[str]:
            for key_field in key_fields:
                if key_field in d and d[key_field]:
                    return str(d[key_field])

            # 递归搜索
            for value in d.values():
                if isinstance(value, dict):
                    result = search_dict(value)
                    if result:
                        return result
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            result = search_dict(item)
                            if result:
                                return result
            return None

        if isinstance(data, dict):
            return search_dict(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    result = search_dict(item)
                    if result:
                        return result

        return None

    def _extract_video_id_from_json(self, data: Any) -> Optional[str]:
        """从 JSON 数据中提取统一的 video_id（用于缓存键）

        优先使用 PlatformDetector 的逻辑生成 video_id

        Args:
            data: JSON 数据

        Returns:
            video_id 或 None
        """
        # 尝试提取关键字段
        key_fields = ['encfilekey', 'm', 'taskid', 'taskId', 'objectId', 'feedId', 'videoId', 'video_id', 'mediaId', 'mediaid', 'objectid', 'feedid']

        def search_dict(d: dict) -> Optional[str]:
            for key_field in key_fields:
                if key_field in d and d[key_field]:
                    value = str(d[key_field])
                    # 使用 PlatformDetector 的逻辑生成 video_id
                    # 模拟 URL: https://dummy.com/?key=value
                    dummy_url = f"https://dummy.com/?{key_field}={value}"
                    video_id = PlatformDetector.extract_video_id(dummy_url)
                    if video_id:
                        return video_id

            # 递归搜索
            for value in d.values():
                if isinstance(value, dict):
                    result = search_dict(value)
                    if result:
                        return result
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            result = search_dict(item)
                            if result:
                                return result
            return None

        if isinstance(data, dict):
            return search_dict(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    result = search_dict(item)
                    if result:
                        return result

        return None

    def request(self, flow) -> None:
        """处理请求（用于诊断）

        Args:
            flow: mitmproxy flow 对象
        """
        if self._handle_channels_inject_script_request(flow):
            return

        if self._handle_channels_inject_proxy_request(flow):
            return

        self.request_count += 1
        self.sniffer.record_request(flow.request.pretty_url)
        client_port = self._get_client_port_from_flow(flow)
        process_name, process_pid = self._lookup_process_info_by_client_port(client_port)
        self.sniffer.note_renderer_process_activity(process_name, process_pid)
        process_suffix = f" process={process_name}" if process_name else ""

        # 非微信视频号相关的请求降级为 DEBUG，减少日志噪声和 GIL 竞争
        url = flow.request.pretty_url
        domain = urlparse(url).netloc.lower() if url else ""
        is_channels_related = any(d in domain for d in [
            'finder.video.qq.com', 'channels.weixin.qq.com', 'finder.weixin.qq.com',
            'weixin.qq.com', 'wechat', 'qpic.cn', 'qlogo.cn',
        ])
        log_level = logging.INFO if is_channels_related else logging.DEBUG

        # 对视频 CDN Range 请求去重：同一 video_id 30 秒内只记录首次
        if is_channels_related and 'stodownload' in url:
            req_video_id = PlatformDetector.extract_video_id(url)
            if req_video_id:
                with self._recent_video_ids_lock:
                    if self._recent_video_ids.get(req_video_id):
                        log_level = logging.DEBUG

        logger.log(
            log_level,
            "[Proxy] Request #%s: %s %s%s",
            self.request_count,
            flow.request.method,
            url[:200] if url else "",
            process_suffix,
        )

    def response(self, flow) -> None:
        """处理响应

        Args:
            flow: mitmproxy flow 对象
        """
        try:
            if self._is_channels_inject_proxy_request(flow) or self._is_channels_inject_script_request(flow):
                return

            self.flow_count += 1
            self.sniffer.record_response_flow()
            original_url = flow.request.pretty_url
            url = PlatformDetector.normalize_channels_video_url(original_url)
            if url != original_url:
                logger.info(f"Normalized fake-ip video URL: {original_url[:120]} -> {url[:120]}")

            # 记录所有请求用于调试
            logger.debug(f"Intercepted request: {url}")

            injected = self._inject_channels_script(flow)
            if not injected:
                injected = self._inject_channels_script_asset(flow)

            # 尝试包裹微信 API 函数（在代理层修改 JS 源码）
            # 注意：必须独立于 inject 运行，因为包含 finderPcFlow 等函数的
            # JS 文件可能恰好是我们注入 hook 脚本的同一个文件
            self._wrap_wechat_api_functions(flow)

            # 每 10 个请求记录一次统计
            if self.flow_count % 10 == 0:
                mode_label = "Local Redirect Mode" if self.sniffer.transparent_mode else "Explicit Proxy Mode"
                logger.info("[%s] Processed %s flows, %s requests", mode_label, self.flow_count, self.request_count)

            # 首先检查是否是微信 API 响应（可能包含视频元数据）
            self._try_extract_api_metadata(flow)
            if injected:
                return

            # 早期去重：在 URL 匹配和日志之前检查，避免 Range 请求日志洪泛
            # 长视频 CDN 会发送数十个 Range 请求，每个都会触发 URL 匹配和日志
            early_video_id = PlatformDetector.extract_video_id(url)
            if early_video_id:
                now = time.time()
                with self._recent_video_ids_lock:
                    last_seen = self._recent_video_ids.get(early_video_id)
                    if last_seen and (now - last_seen) < 30.0:
                        return
                    # 暂不设置时间戳，等确认是视频 URL 后再设置
                    pass

            # 使用 VideoURLExtractor 检查是否是视频号 URL
            is_video_url = self._video_url_extractor.is_video_url(url)

            if not is_video_url:
                # 备用检查：使用 PlatformDetector
                if not PlatformDetector.is_channels_video_url(url):
                    # 额外检查：只对腾讯/微信相关域名进行扩展名检测
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc.lower()
                    is_tencent_domain = any(d in domain for d in ['qq.com', 'weixin.qq.com', 'wechat.com', 'qpic.cn'])

                    if not is_tencent_domain or not PlatformDetector.is_video_url_by_extension(url):
                        return
                    logger.info(f"URL matched by extension on Tencent domain: {url[:120]}")
                else:
                    logger.info(f"Matched channels video URL (PlatformDetector): {url[:120]}")
            else:
                logger.info(f"Matched channels video URL (VideoURLExtractor): {url[:120]}")

            # 确认是视频 URL，设置去重时间戳
            if early_video_id:
                now = time.time()
                with self._recent_video_ids_lock:
                    self._recent_video_ids[early_video_id] = now
                    # 清理过期条目（超过 60 秒）
                    expired = [k for k, v in self._recent_video_ids.items() if (now - v) > 60.0]
                    for k in expired:
                        del self._recent_video_ids[k]

            # 检查 Content-Type（更宽松的检查）
            content_type = flow.response.headers.get("Content-Type", "")
            content_length = flow.response.headers.get("Content-Length", "0")
            request_method = getattr(flow.request, "method", None)
            if not isinstance(request_method, str) or not request_method.strip():
                request_method = "GET"
            request_method = request_method.upper()

            # 明确的图片类型直接跳过，不可能是视频
            ct_lower = content_type.lower()
            if ct_lower.startswith("image/"):
                logger.debug("跳过图片类型响应: %s, Content-Type: %s", url[:120], content_type)
                return

            # 如果是视频号域名，即使 Content-Type 不匹配也尝试添加
            is_video_domain = PlatformDetector.is_channels_video_url(url)
            is_video_type = PlatformDetector.is_video_content_type(content_type)
            try:
                content_length_int = int(content_length)
            except (TypeError, ValueError):
                content_length_int = 0
            is_large_file = content_length_int > 100000  # 大于 100KB

            if not is_video_type and not is_video_domain:
                logger.debug(f"Content-Type not matched: {content_type} for URL: {url}")
                return

            # 对于视频号域名，即使 Content-Type 不是视频也记录（可能是加密的）
            if is_video_domain and not is_video_type:
                if self._cache_thumbnail_from_image(url, content_type):
                    return
                if is_large_file:
                    logger.info(f"Large file from video domain (may be encrypted): {url}, size: {content_length}")
                else:
                    logger.debug(f"Small file from video domain, skipping: {url}")
                    return

            # Avoid recycling WeChat renderers for thumbnail/image probes or HEAD prefetches.
            if request_method != "HEAD" and not self.sniffer.has_channels_page_injection():
                self._schedule_page_metadata_prefetch(flow, url)
                self.sniffer.maybe_recycle_wechat_renderer(
                    "video_stream_without_channels_injection",
                    url,
                )

            # 过滤过小的响应：小于 1KB 不可能是视频（可能是 CDN 错误/重定向响应）
            if content_length_int > 0 and content_length_int < 1024:
                logger.debug("跳过过小的响应 (%s bytes): %s", content_length_int, url[:120])
                return

            if is_video_type:
                logger.info(f"Matched video content type: {content_type}")

            # 提取视频 ID
            video_id = PlatformDetector.extract_video_id(url)
            if not video_id:
                video_id = hashlib.md5(url.encode()).hexdigest()[:16]

            # 解析 URL（提前解析，供后续使用）
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)

            # 尝试从缓存中获取元数据
            metadata = None

            # 尝试使用多种方式查找缓存的元数据
            # 优先使用 video_id 作为缓存键，确保一致性
            cache_keys = [video_id]  # 首先使用统一的 video_id

            # 添加 URL 参数作为备用键
            for key_param in [
                'encfilekey', 'm', 'taskid', 'taskId',
                'objectid', 'feedid', 'objectId', 'feedId',
                'filekey', 'videoId', 'video_id', 'mediaId', 'mediaid',
            ]:
                if key_param in query_params:
                    value = query_params[key_param][0]
                    if value and value not in cache_keys:
                        cache_keys.append(value)

            # 对长 encfilekey 添加截断前缀版本，用于跨清晰度模糊匹配
            for key in list(cache_keys):
                if len(key) > 40:
                    prefix_key = f"pfx:{key[:36]}"
                    if prefix_key not in cache_keys:
                        cache_keys.append(prefix_key)

            # 尝试所有可能的缓存键
            with self._metadata_cache_lock:
                for cache_key in cache_keys:
                    metadata = self._metadata_cache.get(cache_key)
                    if metadata:
                        logger.info(f"使用缓存的元数据 (key={cache_key[:16]}...): title={metadata.title}, thumbnail={metadata.thumbnail}")
                        break

            # 如果缓存中没有，尝试从响应头中提取基本信息
            if not metadata:
                headers = dict(flow.response.headers)
                metadata = PlatformDetector.extract_metadata_from_response(
                    url, headers, b""  # 不传递响应体，因为是视频二进制数据
                )
                if metadata and (metadata.filesize or metadata.resolution):
                    logger.info(f"从响应头提取元数据: filesize={metadata.filesize}, resolution={metadata.resolution}")
                    # 将提取的元数据也缓存起来（使用所有可能的键）
                    with self._metadata_cache_lock:
                        now = time.time()
                        for cache_key in cache_keys:
                            self._metadata_cache[cache_key] = metadata
                            self._metadata_cache_timestamps[cache_key] = now

            # Fallback: 精确键和前缀键都失败时，使用最近10秒内缓存的元数据
            recent_metadata = None
            if (
                not metadata
                or not metadata.decode_key
                or not metadata.title
                or not metadata.thumbnail
            ):
                recent_metadata = self._find_related_recent_cached_metadata(
                    max_age_seconds=10.0,
                    baseline=metadata,
                )
                if recent_metadata:
                    if not metadata:
                        metadata = recent_metadata
                    else:
                        # 合并：只填充缺失的字段
                        if not metadata.title and recent_metadata.title:
                            metadata.title = recent_metadata.title
                        if not metadata.thumbnail and recent_metadata.thumbnail:
                            metadata.thumbnail = recent_metadata.thumbnail
                        # 不从 fallback 借用 decode_key：每个画质/URL 有独立加密密钥
                        # if not metadata.decode_key and recent_metadata.decode_key:
                        #     metadata.decode_key = recent_metadata.decode_key
                        if metadata.duration is None and recent_metadata.duration is not None:
                            metadata.duration = recent_metadata.duration
                        if metadata.filesize is None and recent_metadata.filesize is not None:
                            metadata.filesize = recent_metadata.filesize

            # 生成标题（优先使用元数据）
            title = None
            # 不设置缩略图，让前端使用本地生成
            thumbnail = None

            if metadata:
                if metadata.title:
                    title = metadata.title
                if metadata.thumbnail:
                    thumbnail = metadata.thumbnail

            # 先做一次标题清洗，避免携带“视频号视频 Cvvj5Ix3”等噪声值
            title = self.sniffer._sanitize_video_title(title)

            # 如果元数据中没有标题，从 URL 参数中提取
            if not title:
                title = self.sniffer._build_fallback_title(video_id, query_params)

            # 最后的保险：如果标题仍然为空，使用默认值
            title = self.sniffer._sanitize_video_title(title)
            if not title:
                title = self.sniffer._build_fallback_title(video_id, query_params)

            # 提取解密密钥：优先从 URL 参数提取，其次用视频自身绑定的 key
            # 不从 fallback 缓存借用 decode_key（每个画质/URL 有独立加密密钥）
            decryption_key = self.sniffer._normalize_decode_key(
                PlatformDetector.extract_decryption_key(url)
            )
            if not decryption_key and metadata and metadata.decode_key:
                # 只有当 metadata 是通过精确键匹配（非 fallback）获取时才使用
                if not recent_metadata or metadata.decode_key != recent_metadata.decode_key:
                    decryption_key = self.sniffer._normalize_decode_key(metadata.decode_key)

            # 详细日志
            logger.info(f"视频信息提取结果:")
            logger.info(f"  - 标题: {title}")
            logger.info(f"  - 缩略图: {thumbnail if thumbnail else '无'}")
            logger.info(f"  - 时长: {metadata.duration if metadata else '无'}")
            logger.info(f"  - 文件大小: {metadata.filesize if metadata else '无'}")
            logger.info(f"  - URL: {url[:100]}...")

            # 创建视频对象
            video = DetectedVideo(
                id=video_id,
                url=url,
                title=title,
                duration=metadata.duration if metadata else None,
                resolution=metadata.resolution if metadata else None,
                filesize=metadata.filesize if metadata else None,
                thumbnail=thumbnail,  # 使用提取的缩略图
                detected_at=datetime.now(),
                encryption_type=self.sniffer._infer_encryption_type(url, decryption_key),
                decryption_key=decryption_key,
            )

            # 添加到列表
            added = self.sniffer.add_detected_video(video)
            if added:
                logger.info(f"✓ 新视频已添加: {title}")
            else:
                logger.info(f"○ 视频已存在，已更新元数据: {title}")

        except Exception:
            logger.exception("Error processing response")
