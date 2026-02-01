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
    VideoMetadata,
)
from .platform_detector import PlatformDetector
from .video_url_extractor import VideoURLExtractor, ExtractedVideo
from .http_monitor import HTTPMonitor, HTTPMonitorAddon


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
        self._video_urls: set = set()  # 用于去重（原始 URL）
        self._video_keys: set = set()  # 归一化后的去重键
        self._started_at: Optional[datetime] = None
        self._error_message: Optional[str] = None

        self._proxy_thread: Optional[Thread] = None
        self._master = None
        self._lock = Lock()

        # 视频检测回调
        self._on_video_detected: Optional[Callable[[DetectedVideo], None]] = None
        
        # 集成 VideoURLExtractor 进行统一URL处理
        self._video_url_extractor = VideoURLExtractor()
        
        # HTTP 监控器（用于提取 encfilekey）
        self._http_monitor: Optional[HTTPMonitor] = None
    
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
        
        # 创建 HTTP 监控器并设置回调
        self._http_monitor = HTTPMonitor(on_video_detected=self._on_http_video_detected)
        
        # 添加插件
        self._master.addons.add(VideoSnifferAddon(self))
        self._master.addons.add(HTTPMonitorAddon(self._http_monitor))

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

                # 移除 mitmproxy 的日志处理器，避免 event loop 关闭后的错误
                try:
                    import logging
                    mitmproxy_logger = logging.getLogger('mitmproxy')
                    # 清除所有处理器
                    for handler in mitmproxy_logger.handlers[:]:
                        try:
                            handler.close()
                            mitmproxy_logger.removeHandler(handler)
                        except Exception:
                            pass
                except Exception:
                    pass

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
            self._video_keys.clear()
            # 同时清除 VideoURLExtractor 的ID缓存
            self._video_url_extractor.clear_extracted_ids()
    
    def get_video_url_extractor(self) -> VideoURLExtractor:
        """获取视频URL提取器实例"""
        return self._video_url_extractor
    
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
            
            # 查找是否已存在
            existing_video = None
            with self._lock:
                for v in self._detected_videos:
                    if v.id == video_id or v.url == url:
                        existing_video = v
                        break
            
            if existing_video:
                # 更新 encfilekey
                if encfilekey and not existing_video.decryption_key:
                    logger.info(f"更新视频 {video_id} 的 encfilekey")
                    self.update_video_metadata(
                        video_id=video_id,
                        decryption_key=encfilekey,
                    )
            else:
                # 创建新视频
                from datetime import datetime
                video = DetectedVideo(
                    id=video_id,
                    url=url,
                    title=f"视频号视频 {video_id[:8]}",
                    thumbnail=None,
                    detected_at=datetime.now(),
                    encryption_type=EncryptionType.XOR,  # 有 encfilekey 说明是加密的
                    decryption_key=encfilekey,
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
            for existing in self._detected_videos:
                if existing.id == video.id or existing.url.strip() == normalized_url:
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
            mapping = {
                "title": title,
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
        
        # 自动生成标题（确保标题永远不为 None）
        if not title:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # 尝试从URL参数提取信息
            if 'feedid' in query_params:
                feed_id = query_params['feedid'][0][:8]
                title = f"视频号视频 {feed_id}"
            elif 'objectid' in query_params:
                obj_id = query_params['objectid'][0][:8]
                title = f"视频号视频 {obj_id}"
            elif 'encfilekey' in query_params:
                key = query_params['encfilekey'][0][:8]
                title = f"视频号视频 {key}"
            else:
                # 使用时间戳
                time_str = datetime.now().strftime("%H:%M:%S")
                title = f"微信视频号 {time_str}"
        
        # 缩略图设置为 None
        # 微信视频号的缩略图URL需要特殊认证，无法直接访问
        # 前端会使用本地生成的缩略图或默认图标
        thumbnail = None
        
        # 创建视频对象
        video = DetectedVideo(
            id=video_id,
            url=url,
            title=title,
            thumbnail=thumbnail,
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
        # 元数据缓存：存储从 API 响应中提取的元数据
        self._metadata_cache: Dict[str, VideoMetadata] = {}
        self._metadata_cache_lock = Lock()

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

    def _try_extract_api_metadata(self, flow) -> None:
        """尝试从 API 响应中提取视频元数据
        
        Args:
            flow: mitmproxy flow 对象
        """
        try:
            url = flow.request.pretty_url
            content_type = flow.response.headers.get("Content-Type", "")
            
            # 调试日志
            logger.debug(f"[META] Checking URL: {url[:80]}, Content-Type: {content_type}")
            
            # 只处理 JSON 响应
            if "json" not in content_type.lower():
                logger.debug(f"[META] Skipping non-JSON response")
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
            
            logger.info(f"[META] WeChat API detected: {domain}")
            
            # 尝试解析 JSON 响应
            try:
                response_text = flow.response.content.decode('utf-8', errors='ignore')
                if not response_text.strip():
                    return
                
                import json
                data = json.loads(response_text)
                
                # 尝试从 JSON 中提取视频元数据
                metadata = self._parse_wechat_api_response(data)
                
                if metadata and (metadata.title or metadata.thumbnail or metadata.filesize):
                    # 存储到缓存中，使用多个键以提高命中率
                    cache_keys = []
                    
                    # 尝试从 URL 中提取各种可能的键
                    query_params = parse_qs(parsed_url.query)
                    for key_param in ['encfilekey', 'objectid', 'feedid', 'objectId', 'feedId']:
                        if key_param in query_params:
                            cache_keys.append(query_params[key_param][0])
                    
                    # 或者从 JSON 数据中提取
                    json_key = self._extract_video_key_from_json(data)
                    if json_key and json_key not in cache_keys:
                        cache_keys.append(json_key)
                    
                    # 使用所有找到的键存储元数据
                    if cache_keys:
                        # 尝试提取 video_id 并作为主键
                        video_id = self._extract_video_id_from_json(data)
                        if video_id:
                            cache_keys.insert(0, video_id)  # video_id 作为首选键
                        
                        with self._metadata_cache_lock:
                            for cache_key in cache_keys:
                                self._metadata_cache[cache_key] = metadata
                        logger.info(f"缓存 API 元数据: title={metadata.title}, thumbnail={metadata.thumbnail}, keys={len(cache_keys)}")
                    else:
                        logger.warning("无法为 API 元数据生成缓存键")
                
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.debug(f"Error parsing API response: {e}")
                
        except Exception as e:
            logger.debug(f"Error extracting API metadata: {e}")
    
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
            'title': ['title', 'desc', 'description', 'nickname', 'name', 'videoTitle', 'video_title'],
            'thumbnail': ['thumbUrl', 'thumb_url', 'cover', 'coverUrl', 'cover_url', 'headUrl', 'head_url', 'thumburl'],
            'duration': ['duration', 'videoTime', 'video_time', 'playDuration', 'play_duration', 'videoDuration'],
            'width': ['width', 'videoWidth', 'video_width'],
            'height': ['height', 'videoHeight', 'video_height'],
            'filesize': ['size', 'fileSize', 'file_size', 'videoSize', 'video_size', 'filesize'],
        }
        
        def extract_from_dict(d: dict, metadata: VideoMetadata) -> None:
            """递归从字典中提取字段"""
            for field, keys in field_mapping.items():
                if getattr(metadata, field) is None:
                    for key in keys:
                        if key in d and d[key]:
                            value = d[key]
                            # 类型转换
                            if field in ['duration', 'width', 'height', 'filesize']:
                                try:
                                    value = int(value)
                                except (ValueError, TypeError):
                                    continue
                            setattr(metadata, field, value)
                            break
            
            # 递归处理嵌套对象
            for value in d.values():
                if isinstance(value, dict):
                    extract_from_dict(value, metadata)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            extract_from_dict(item, metadata)
        
        if isinstance(data, dict):
            extract_from_dict(data, metadata)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    extract_from_dict(item, metadata)
        
        # 计算分辨率
        if metadata.resolution is None and metadata.width and metadata.height:
            if metadata.height >= 1080:
                metadata.resolution = '1080p'
            elif metadata.height >= 720:
                metadata.resolution = '720p'
            elif metadata.height >= 480:
                metadata.resolution = '480p'
            else:
                metadata.resolution = f'{metadata.height}p'
        
        return metadata if (metadata.title or metadata.thumbnail or metadata.filesize) else None
    
    def _extract_video_key_from_json(self, data: Any) -> Optional[str]:
        """从 JSON 数据中提取视频密钥
        
        Args:
            data: JSON 数据
            
        Returns:
            视频密钥或 None
        """
        key_fields = ['encfilekey', 'filekey', 'videoId', 'video_id', 'objectId', 'feedId']
        
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
        key_fields = ['encfilekey', 'objectId', 'feedId', 'videoId', 'video_id']
        
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

            # 首先检查是否是微信 API 响应（可能包含视频元数据）
            self._try_extract_api_metadata(flow)

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
            
            # 解析 URL（提前解析，供后续使用）
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            # 尝试从缓存中获取元数据
            metadata = None
            
            # 尝试使用多种方式查找缓存的元数据
            # 优先使用 video_id 作为缓存键，确保一致性
            cache_keys = [video_id]  # 首先使用统一的 video_id
            
            # 添加 URL 参数作为备用键
            if 'encfilekey' in query_params:
                cache_keys.append(query_params['encfilekey'][0])
            if 'objectid' in query_params:
                cache_keys.append(query_params['objectid'][0])
            if 'feedid' in query_params:
                cache_keys.append(query_params['feedid'][0])
            
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
                        for cache_key in cache_keys:
                            self._metadata_cache[cache_key] = metadata
            
            # 生成标题（优先使用元数据）
            title = None
            # 不设置缩略图，让前端使用本地生成
            thumbnail = None

            if metadata:
                if metadata.title:
                    title = metadata.title
                if metadata.thumbnail:
                    thumbnail = metadata.thumbnail
            
            # 如果元数据中没有标题，从 URL 参数中提取
            if not title:
                try:
                    # 尝试从URL参数提取信息
                    if 'feedid' in query_params:
                        feed_id = query_params['feedid'][0][:8]
                        title = f"视频号视频 {feed_id}"
                    elif 'objectid' in query_params:
                        obj_id = query_params['objectid'][0][:8]
                        title = f"视频号视频 {obj_id}"
                    elif 'encfilekey' in query_params:
                        # 使用 encfilekey 的前8位作为标识
                        key = query_params['encfilekey'][0][:8]
                        title = f"视频号视频 {key}"
                    else:
                        # 使用时间戳生成标题
                        time_str = datetime.now().strftime("%H:%M:%S")
                        title = f"微信视频号 {time_str}"
                except Exception:
                    # 使用默认标题
                    time_str = datetime.now().strftime("%H:%M:%S")
                    title = f"微信视频号 {time_str}"
            
            # 最后的保险：如果标题仍然为空，使用默认值
            if not title:
                title = f"微信视频号 {datetime.now().strftime('%H:%M:%S')}"
            
            # 提取解密密钥
            decryption_key = PlatformDetector.extract_decryption_key(url)
            
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
                encryption_type=EncryptionType.UNKNOWN,
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
