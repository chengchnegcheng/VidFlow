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
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from threading import Thread, Lock
from urllib.parse import urlparse, parse_qs

from .models import (
    SnifferState,
    SnifferStatus,
    SnifferStartResult,
    DetectedVideo,
    EncryptionType,
    ErrorCode,
    get_error_message,
)
from .platform_detector import PlatformDetector
from .video_url_extractor import VideoURLExtractor, ExtractedVideo


logger = logging.getLogger(__name__)


class ProxySniffer:
    """代理嗅探器
    
    使用 mitmproxy 实现 HTTP/HTTPS 代理，自动识别视频号视频 URL。
    集成 VideoURLExtractor 进行统一的URL处理和去重。
    
    Validates: Requirements 6.2, 6.3
    """
    
    def __init__(self, port: int = 8888, cert_dir: Optional[Path] = None, transparent_mode: bool = False):
        """初始化代理嗅探器

        Args:
            port: 代理端口
            cert_dir: 证书目录
            transparent_mode: 是否使用透明代理模式（用于 WinDivert 透明捕获）
        """
        self.port = port
        self.cert_dir = cert_dir
        self.transparent_mode = transparent_mode

        self._state = SnifferState.STOPPED
        self._detected_videos: List[DetectedVideo] = []
        self._video_urls: set = set()  # 用于去重
        self._started_at: Optional[datetime] = None
        self._error_message: Optional[str] = None

        self._proxy_thread: Optional[Thread] = None
        self._master = None
        self._lock = Lock()

        # 视频检测回调
        self._on_video_detected: Optional[Callable[[DetectedVideo], None]] = None
        
        # 集成 VideoURLExtractor 进行统一URL处理
        self._video_url_extractor = VideoURLExtractor()
    
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
        
        try:
            # 启动代理线程
            self._proxy_thread = Thread(target=self._run_proxy, daemon=True)
            self._proxy_thread.start()
            
            # 等待代理启动
            for _ in range(50):  # 最多等待 5 秒
                await asyncio.sleep(0.1)
                if self._state == SnifferState.RUNNING:
                    break
                if self._state == SnifferState.ERROR:
                    return SnifferStartResult(
                        success=False,
                        error_message=self._error_message or "代理启动失败"
                    )
            
            if self._state != SnifferState.RUNNING:
                self._state = SnifferState.ERROR
                self._error_message = "代理启动超时"
                return SnifferStartResult(
                    success=False,
                    error_message=self._error_message
                )
            
            self._started_at = datetime.now()
            
            return SnifferStartResult(
                success=True,
                proxy_address=f"127.0.0.1:{self.port}"
            )
            
        except PermissionError:
            self._state = SnifferState.ERROR
            self._error_message = get_error_message(ErrorCode.PERMISSION_DENIED)
            return SnifferStartResult(
                success=False,
                error_message=self._error_message,
                error_code=ErrorCode.PERMISSION_DENIED
            )
        except Exception as e:
            self._state = SnifferState.ERROR
            self._error_message = f"启动失败: {str(e)}"
            logger.exception("Failed to start proxy")
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

            # 在事件循环中运行异步初始化和代理
            loop.run_until_complete(self._async_run_proxy())

        except Exception as e:
            self._state = SnifferState.ERROR
            self._error_message = str(e)
            logger.exception("Proxy error")
        finally:
            # 清理事件循环中的所有待处理任务
            if loop:
                try:
                    # 取消所有待处理的任务
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()

                    # 等待所有任务完成取消
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                    # 关闭事件循环
                    loop.close()
                except Exception as e:
                    logger.debug(f"Error cleaning up event loop: {e}")
    
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
            opts.mode = ["local:WeChat.exe,WeChatAppEx.exe"]
            logger.info(f"Starting mitmproxy in local mode (auto WinDivert) targeting WeChat processes")
        else:
            # 显式代理模式：期望客户端配置代理并发送 CONNECT 请求
            logger.info(f"Starting mitmproxy in regular (explicit) mode on port {self.port}")

        # 如果有证书目录，设置证书路径
        if self.cert_dir:
            opts.confdir = str(self.cert_dir)

        self._master = DumpMaster(opts)
        self._master.addons.add(VideoSnifferAddon(self))

        self._state = SnifferState.RUNNING

        # 运行代理
        await self._master.run()
    
    async def stop(self) -> bool:
        """停止代理服务器

        Returns:
            停止成功返回 True
        """
        if self._state == SnifferState.STOPPED:
            return True

        if self._state == SnifferState.STOPPING:
            return False

        self._state = SnifferState.STOPPING

        try:
            if self._master:
                # 先关闭 master
                self._master.shutdown()

                # 等待 master 完全停止，增加等待时间
                for _ in range(30):  # 最多等待 3 秒
                    await asyncio.sleep(0.1)
                    # 检查 master 是否已经停止
                    if not hasattr(self._master, 'should_exit') or self._master.should_exit.is_set():
                        break

                self._master = None

            # 等待线程结束，增加超时时间
            if self._proxy_thread and self._proxy_thread.is_alive():
                self._proxy_thread.join(timeout=10)

                # 如果线程还在运行，强制标记为停止
                if self._proxy_thread.is_alive():
                    logger.warning("Proxy thread did not stop gracefully")

            self._proxy_thread = None
            self._state = SnifferState.STOPPED
            self._started_at = None

            # 等待端口释放
            for _ in range(20):  # 最多等待 2 秒
                if self._is_port_available(self.port):
                    break
                await asyncio.sleep(0.1)

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
            # 同时清除 VideoURLExtractor 的ID缓存
            self._video_url_extractor.clear_extracted_ids()
    
    def get_video_url_extractor(self) -> VideoURLExtractor:
        """获取视频URL提取器实例"""
        return self._video_url_extractor
    
    def is_video_url(self, url: str) -> bool:
        """检查URL是否是视频号相关的视频URL
        
        使用 VideoURLExtractor 进行统一检查。
        
        Args:
            url: URL字符串
            
        Returns:
            是否是视频URL
        """
        return self._video_url_extractor.is_video_url(url)
    
    def add_detected_video(self, video: DetectedVideo) -> bool:
        """添加检测到的视频
        
        Args:
            video: 检测到的视频
            
        Returns:
            如果是新视频返回 True，如果是重复的返回 False
        """
        with self._lock:
            # 检查是否重复（按视频 ID 去重，而不是 URL）
            if video.id in {v.id for v in self._detected_videos}:
                return False
            
            self._video_urls.add(video.url)
            self._detected_videos.append(video)
            
            # 触发回调
            if self._on_video_detected:
                try:
                    self._on_video_detected(video)
                except Exception:
                    logger.exception("Error in video detected callback")
            
            return True
    
    def add_video_from_url(self, url: str, title: Optional[str] = None) -> Optional[DetectedVideo]:
        """从 URL 手动添加视频
        
        Args:
            url: 视频 URL
            title: 可选的视频标题
            
        Returns:
            添加成功返回视频对象，失败返回 None
        """
        # 验证 URL
        if not url or not url.startswith(('http://', 'https://')):
            logger.warning(f"Invalid URL: {url}")
            return None
        
        # 提取视频 ID
        video_id = PlatformDetector.extract_video_id(url)
        if not video_id:
            video_id = hashlib.md5(url.encode()).hexdigest()[:16]
        
        # 提取解密密钥
        decryption_key = PlatformDetector.extract_decryption_key(url)
        
        # 自动生成标题
        if not title:
            parsed = urlparse(url)
            domain = parsed.netloc
            title = f"视频号视频 ({domain})"
        
        # 创建视频对象
        video = DetectedVideo(
            id=video_id,
            url=url,
            title=title,
            detected_at=datetime.now(),
            encryption_type=EncryptionType.UNKNOWN,
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


class VideoSnifferAddon:
    """mitmproxy 插件，用于嗅探视频 URL
    
    集成 VideoURLExtractor 进行统一的URL模式匹配。
    """

    def __init__(self, sniffer: ProxySniffer):
        self.sniffer = sniffer
        self.request_count = 0
        self.flow_count = 0
        self.error_count = 0
        # 使用 sniffer 的 VideoURLExtractor 实例
        self._video_url_extractor = sniffer.get_video_url_extractor()

    def load(self, loader):
        """插件加载时调用"""
        logger.info("VideoSnifferAddon loaded")

    def running(self):
        """mitmproxy 开始运行时调用"""
        logger.info("VideoSnifferAddon running")

    def client_connected(self, client):
        """客户端连接时调用"""
        logger.info(f"Client connected: {client.peername}")

    def client_disconnected(self, client):
        """客户端断开时调用"""
        logger.debug(f"Client disconnected: {client.peername}")

    def server_connect(self, data):
        """连接到服务器时调用"""
        logger.info(f"Connecting to server: {data.server.address}")

    def server_connected(self, data):
        """连接到服务器成功时调用"""
        logger.info(f"Connected to server: {data.server.address}")

    def tls_clienthello(self, data):
        """收到 TLS ClientHello 时调用"""
        try:
            sni = data.client_hello.sni
            logger.info(f"TLS ClientHello received, SNI: {sni}")
        except Exception as e:
            logger.warning(f"Error extracting SNI: {e}")

    def tls_start_client(self, data):
        """开始客户端 TLS 握手时调用"""
        logger.info(f"TLS start client: {data.context.client.peername}")

    def tls_start_server(self, data):
        """开始服务器 TLS 握手时调用"""
        logger.info(f"TLS start server: {data.context.server.address}")

    def error(self, flow):
        """发生错误时调用"""
        self.error_count += 1
        logger.error(f"Flow error #{self.error_count}: {flow.error}")

    def request(self, flow) -> None:
        """处理请求（用于诊断）

        Args:
            flow: mitmproxy flow 对象
        """
        self.request_count += 1
        logger.info(f"[Proxy] Request #{self.request_count}: {flow.request.method} {flow.request.pretty_url}")

    def response(self, flow) -> None:
        """处理响应

        Args:
            flow: mitmproxy flow 对象
        """
        try:
            self.flow_count += 1
            url = flow.request.pretty_url

            # 记录所有请求用于调试
            logger.debug(f"Intercepted request: {url}")

            # 每 10 个请求记录一次统计
            if self.flow_count % 10 == 0:
                logger.info(f"[Transparent Mode] Processed {self.flow_count} flows, {self.request_count} requests")

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
                    logger.info(f"URL matched by extension on Tencent domain: {url}")
                else:
                    logger.info(f"Matched channels video URL (PlatformDetector): {url}")
            else:
                logger.info(f"Matched channels video URL (VideoURLExtractor): {url}")

            # 检查 Content-Type（更宽松的检查）
            content_type = flow.response.headers.get("Content-Type", "")
            content_length = flow.response.headers.get("Content-Length", "0")
            
            # 如果是视频号域名，即使 Content-Type 不匹配也尝试添加
            is_video_domain = PlatformDetector.is_channels_video_url(url)
            is_video_type = PlatformDetector.is_video_content_type(content_type)
            is_large_file = int(content_length) > 100000  # 大于 100KB
            
            if not is_video_type and not is_video_domain:
                logger.debug(f"Content-Type not matched: {content_type} for URL: {url}")
                return
            
            # 对于视频号域名，即使 Content-Type 不是视频也记录（可能是加密的）
            if is_video_domain and not is_video_type:
                if is_large_file:
                    logger.info(f"Large file from video domain (may be encrypted): {url}, size: {content_length}")
                else:
                    logger.debug(f"Small file from video domain, skipping: {url}")
                    return

            if is_video_type:
                logger.info(f"Matched video content type: {content_type}")
            
            # 提取视频 ID
            video_id = PlatformDetector.extract_video_id(url)
            if not video_id:
                video_id = hashlib.md5(url.encode()).hexdigest()[:16]
            
            # 提取元数据
            headers = dict(flow.response.headers)
            metadata = PlatformDetector.extract_metadata_from_response(
                url, headers, b""
            )
            
            # 生成更好的默认标题（使用英文避免编码问题）
            title = "WeChat Channels Video"  # 默认标题
            if metadata and metadata.title:
                title = metadata.title
            else:
                # 从 URL 参数中提取有用信息作为标题
                try:
                    parsed_url = urlparse(url)
                    query_params = parse_qs(parsed_url.query)
                    
                    # 尝试从 X-snsvideoflag 参数获取信息
                    video_flag = query_params.get('X-snsvideoflag', [None])[0]
                    if video_flag:
                        title = f"WeChat Video ({video_flag})"
                    else:
                        # 使用视频ID的前8位作为标识
                        if video_id and len(video_id) >= 8:
                            title = f"WeChat Video ({video_id[:8]})"
                except Exception:
                    pass  # 使用默认标题
            
            # 提取解密密钥
            decryption_key = PlatformDetector.extract_decryption_key(url)
            
            # 创建视频对象
            video = DetectedVideo(
                id=video_id,
                url=url,
                title=title,
                duration=metadata.duration if metadata else None,
                resolution=metadata.resolution if metadata else None,
                filesize=metadata.filesize if metadata else None,
                thumbnail=None,
                detected_at=datetime.now(),
                encryption_type=EncryptionType.UNKNOWN,
                decryption_key=decryption_key,
            )
            
            # 添加到列表
            self.sniffer.add_detected_video(video)
            logger.info(f"Detected video: {title} - {url[:100]}...")
            
        except Exception:
            logger.exception("Error processing response")
