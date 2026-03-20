"""
视频元数据提取器

从多个来源提取视频元数据：
1. HTTP HEAD 请求获取文件大小、Content-Type
2. 解析微信 API 响应（JSON）提取标题、缩略图
3. 使用 yt-dlp 提取完整元数据

Author: VidFlow Team
Date: 2025-01-19
"""

import re
import json
import logging
import asyncio
import aiohttp
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """视频元数据"""
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None  # 秒
    resolution: Optional[str] = None
    filesize: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    fps: Optional[float] = None
    description: Optional[str] = None
    uploader: Optional[str] = None
    upload_date: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "title": self.title,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "resolution": self.resolution,
            "filesize": self.filesize,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "codec": self.codec,
            "bitrate": self.bitrate,
            "fps": self.fps,
            "description": self.description,
            "uploader": self.uploader,
            "upload_date": self.upload_date,
            "view_count": self.view_count,
            "like_count": self.like_count,
        }


class VideoMetadataExtractor:
    """视频元数据提取器

    支持多种提取方式：
    1. HTTP HEAD 请求
    2. 微信 API 响应解析
    3. yt-dlp 提取
    """

    # 微信 API 响应模式
    WECHAT_API_PATTERNS = [
        r'finder\.video\.qq\.com/.*\.json',
        r'channels\.weixin\.qq\.com/cgi-bin',
        r'mp\.weixin\.qq\.com/.*getmsg',
    ]

    # 视频信息字段映射
    WECHAT_FIELD_MAPPING = {
        'title': ['title', 'desc', 'description', 'nickname', 'name'],
        'thumbnail': ['thumbUrl', 'thumb_url', 'cover', 'coverUrl', 'cover_url', 'headUrl', 'head_url'],
        'duration': ['duration', 'videoTime', 'video_time', 'playDuration', 'play_duration'],
        'width': ['width', 'videoWidth', 'video_width'],
        'height': ['height', 'videoHeight', 'video_height'],
        'filesize': ['size', 'fileSize', 'file_size', 'videoSize', 'video_size'],
        'view_count': ['readCount', 'read_count', 'playCount', 'play_count', 'viewCount', 'view_count'],
        'like_count': ['likeCount', 'like_count', 'favCount', 'fav_count'],
        'uploader': ['nickname', 'userName', 'user_name', 'author', 'authorName', 'author_name'],
    }

    def __init__(self, timeout: int = 10, max_retries: int = 2):
        """初始化

        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

        # 编译正则表达式
        self._api_patterns = [re.compile(p, re.IGNORECASE) for p in self.WECHAT_API_PATTERNS]

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) XWEB/9129',
                }
            )
        return self._session

    async def close(self):
        """关闭 session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def extract_from_url(self, url: str) -> Optional[VideoMetadata]:
        """从视频 URL 提取元数据（通过 HEAD 请求）

        Args:
            url: 视频 URL

        Returns:
            视频元数据，如果提取失败则返回 None
        """
        try:
            session = await self._get_session()

            for attempt in range(self.max_retries):
                try:
                    async with session.head(url, allow_redirects=True) as response:
                        if response.status == 200:
                            metadata = VideoMetadata()

                            # 提取文件大小
                            content_length = response.headers.get('Content-Length')
                            if content_length:
                                try:
                                    metadata.filesize = int(content_length)
                                except ValueError:
                                    pass

                            # 提取格式
                            content_type = response.headers.get('Content-Type', '')
                            if 'video' in content_type:
                                # 例如: video/mp4, video/x-flv
                                parts = content_type.split('/')
                                if len(parts) > 1:
                                    metadata.format = parts[1].split(';')[0].strip()

                            # 从 URL 提取分辨率
                            metadata.resolution = self._extract_resolution_from_url(url)

                            logger.info(f"Extracted metadata from URL HEAD: filesize={metadata.filesize}, format={metadata.format}")
                            return metadata

                        elif response.status == 403 or response.status == 401:
                            logger.warning(f"Access denied for URL: {url}")
                            return None

                except asyncio.TimeoutError:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    logger.warning(f"Timeout extracting metadata from URL: {url}")
                    return None

        except Exception as e:
            logger.error(f"Failed to extract metadata from URL: {e}")
            return None

    def _extract_resolution_from_url(self, url: str) -> Optional[str]:
        """从 URL 中提取分辨率信息

        Args:
            url: 视频 URL

        Returns:
            分辨率字符串，如 "1080p"
        """
        patterns = [
            (r'1080[pP]', '1080p'),
            (r'720[pP]', '720p'),
            (r'480[pP]', '480p'),
            (r'360[pP]', '360p'),
            (r'4[kK]', '4K'),
            (r'2[kK]', '2K'),
            (r'_(\d{3,4})x(\d{3,4})', None),  # 宽x高格式
        ]

        for pattern, resolution in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                if resolution:
                    return resolution
                else:
                    # 从宽高计算分辨率
                    width, height = int(match.group(1)), int(match.group(2))
                    if height >= 1080:
                        return '1080p'
                    elif height >= 720:
                        return '720p'
                    elif height >= 480:
                        return '480p'
                    else:
                        return f'{height}p'

        return None

    def is_wechat_api_response(self, url: str) -> bool:
        """判断是否为微信 API 响应

        Args:
            url: URL

        Returns:
            是否为微信 API 响应
        """
        for pattern in self._api_patterns:
            if pattern.search(url):
                return True
        return False

    def extract_from_json(self, json_data: str) -> Optional[VideoMetadata]:
        """从 JSON 数据中提取元数据

        Args:
            json_data: JSON 字符串

        Returns:
            视频元数据，如果提取失败则返回 None
        """
        try:
            data = json.loads(json_data)
            return self._parse_wechat_json(data)
        except json.JSONDecodeError:
            logger.debug("Failed to parse JSON data")
            return None
        except Exception as e:
            logger.error(f"Failed to extract metadata from JSON: {e}")
            return None

    def extract_from_http_response(self, response_body: bytes) -> Optional[VideoMetadata]:
        """从 HTTP 响应体中提取元数据

        Args:
            response_body: HTTP 响应体

        Returns:
            视频元数据，如果提取失败则返回 None
        """
        try:
            # 尝试解码为文本
            text = response_body.decode('utf-8', errors='ignore')

            # 尝试解析为 JSON
            if text.strip().startswith('{') or text.strip().startswith('['):
                return self.extract_from_json(text)

            # 尝试从 HTML 中提取 JSON
            json_pattern = re.compile(r'<script[^>]*>\s*(?:var\s+\w+\s*=\s*)?(\{[^<]+\})\s*</script>', re.DOTALL)
            matches = json_pattern.findall(text)

            for match in matches:
                metadata = self.extract_from_json(match)
                if metadata and (metadata.title or metadata.thumbnail):
                    return metadata

            return None

        except Exception as e:
            logger.error(f"Failed to extract metadata from HTTP response: {e}")
            return None

    def _parse_wechat_json(self, data: Any, metadata: Optional[VideoMetadata] = None) -> Optional[VideoMetadata]:
        """递归解析微信 JSON 数据

        Args:
            data: JSON 数据（dict 或 list）
            metadata: 已有的元数据对象

        Returns:
            视频元数据
        """
        if metadata is None:
            metadata = VideoMetadata()

        if isinstance(data, dict):
            # 提取各个字段
            for field, keys in self.WECHAT_FIELD_MAPPING.items():
                if getattr(metadata, field) is None:  # 只在字段为空时提取
                    for key in keys:
                        if key in data:
                            value = data[key]
                            if value:
                                # 类型转换
                                if field in ['duration', 'width', 'height', 'filesize', 'view_count', 'like_count']:
                                    try:
                                        value = int(value)
                                    except (ValueError, TypeError):
                                        continue

                                setattr(metadata, field, value)
                                break

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

            # 递归处理嵌套对象
            for value in data.values():
                if isinstance(value, (dict, list)):
                    self._parse_wechat_json(value, metadata)

        elif isinstance(data, list):
            # 递归处理列表
            for item in data:
                if isinstance(item, (dict, list)):
                    self._parse_wechat_json(item, metadata)

        return metadata if (metadata.title or metadata.thumbnail) else None

    async def extract_with_ytdlp(self, url: str) -> Optional[VideoMetadata]:
        """使用 yt-dlp 提取元数据

        Args:
            url: 视频 URL

        Returns:
            视频元数据，如果提取失败则返回 None
        """
        try:
            import yt_dlp

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'socket_timeout': self.timeout,
                'retries': self.max_retries,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )

                if not info:
                    return None

                metadata = VideoMetadata()

                # 提取基本信息
                metadata.title = info.get('title')
                metadata.thumbnail = info.get('thumbnail')
                metadata.duration = info.get('duration')
                metadata.description = info.get('description')
                metadata.uploader = info.get('uploader') or info.get('channel')
                metadata.upload_date = info.get('upload_date')
                metadata.view_count = info.get('view_count')
                metadata.like_count = info.get('like_count')

                # 提取视频格式信息
                metadata.width = info.get('width')
                metadata.height = info.get('height')
                metadata.format = info.get('ext')
                metadata.filesize = info.get('filesize') or info.get('filesize_approx')
                metadata.fps = info.get('fps')

                # 提取编码信息
                if 'vcodec' in info:
                    metadata.codec = info['vcodec']

                # 提取比特率
                if 'tbr' in info:
                    metadata.bitrate = int(info['tbr'] * 1000)  # 转换为 bps

                # 计算分辨率
                if metadata.height:
                    if metadata.height >= 2160:
                        metadata.resolution = '4K'
                    elif metadata.height >= 1440:
                        metadata.resolution = '2K'
                    elif metadata.height >= 1080:
                        metadata.resolution = '1080p'
                    elif metadata.height >= 720:
                        metadata.resolution = '720p'
                    elif metadata.height >= 480:
                        metadata.resolution = '480p'
                    else:
                        metadata.resolution = f'{metadata.height}p'

                logger.info(f"Extracted metadata with yt-dlp: title={metadata.title}, resolution={metadata.resolution}")
                return metadata

        except ImportError:
            logger.warning("yt-dlp not installed, skipping yt-dlp extraction")
            return None
        except Exception as e:
            logger.debug(f"Failed to extract metadata with yt-dlp: {e}")
            return None

    async def extract_comprehensive(
        self,
        url: str,
        try_ytdlp: bool = True,
        http_response: Optional[bytes] = None
    ) -> Optional[VideoMetadata]:
        """综合提取元数据

        按优先级尝试多种方式：
        1. 如果有 HTTP 响应体，先尝试解析
        2. 尝试 HEAD 请求
        3. 如果启用，尝试 yt-dlp

        Args:
            url: 视频 URL
            try_ytdlp: 是否尝试使用 yt-dlp
            http_response: HTTP 响应体（如果有）

        Returns:
            视频元数据，如果所有方式都失败则返回 None
        """
        metadata = VideoMetadata()

        # 1. 尝试从 HTTP 响应体提取
        if http_response:
            response_metadata = self.extract_from_http_response(http_response)
            if response_metadata:
                metadata = self._merge_metadata(metadata, response_metadata)
                logger.info("Extracted metadata from HTTP response")

        # 2. 尝试 HEAD 请求
        if not metadata.filesize or not metadata.format:
            head_metadata = await self.extract_from_url(url)
            if head_metadata:
                metadata = self._merge_metadata(metadata, head_metadata)

        # 3. 尝试 yt-dlp（如果启用且还缺少关键信息）
        if try_ytdlp and (not metadata.title or not metadata.thumbnail):
            ytdlp_metadata = await self.extract_with_ytdlp(url)
            if ytdlp_metadata:
                metadata = self._merge_metadata(metadata, ytdlp_metadata)

        # 如果至少有一些信息，返回元数据
        if any([
            metadata.title,
            metadata.thumbnail,
            metadata.filesize,
            metadata.duration,
            metadata.resolution,
        ]):
            return metadata

        return None

    def _merge_metadata(self, base: VideoMetadata, new: VideoMetadata) -> VideoMetadata:
        """合并两个元数据对象（优先使用非空值）

        Args:
            base: 基础元数据
            new: 新元数据

        Returns:
            合并后的元数据
        """
        for field in [
            'title', 'thumbnail', 'duration', 'resolution', 'filesize',
            'width', 'height', 'format', 'codec', 'bitrate', 'fps',
            'description', 'uploader', 'upload_date', 'view_count', 'like_count'
        ]:
            base_value = getattr(base, field)
            new_value = getattr(new, field)

            # 如果基础值为空，使用新值
            if base_value is None and new_value is not None:
                setattr(base, field, new_value)

        return base


# 全局实例
_metadata_extractor: Optional[VideoMetadataExtractor] = None


def get_metadata_extractor() -> VideoMetadataExtractor:
    """获取全局元数据提取器实例"""
    global _metadata_extractor
    if _metadata_extractor is None:
        _metadata_extractor = VideoMetadataExtractor()
    return _metadata_extractor


async def extract_video_metadata(
    url: str,
    try_ytdlp: bool = False,
    http_response: Optional[bytes] = None
) -> Optional[VideoMetadata]:
    """提取视频元数据（便捷函数）

    Args:
        url: 视频 URL
        try_ytdlp: 是否尝试使用 yt-dlp
        http_response: HTTP 响应体（如果有）

    Returns:
        视频元数据，如果提取失败则返回 None
    """
    extractor = get_metadata_extractor()
    return await extractor.extract_comprehensive(url, try_ytdlp, http_response)
