"""
微信视频号平台检测器

识别视频号相关的网络请求 URL，提取视频 ID 和元数据。
"""

import re
import hashlib
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from .models import VideoMetadata


class PlatformDetector:
    """视频号 URL 检测器"""
    
    # 视频号相关域名模式（2025年更新）
    VIDEO_PATTERNS = [
        # 主要视频域名
        r'finder\.video\.qq\.com',
        r'findermp\.video\.qq\.com',
        r'findervideodownload\.video\.qq\.com',
        # 微信渠道域名
        r'channels\.weixin\.qq\.com',
        r'szextshort\.weixin\.qq\.com.*finder',
        r'szshort\.weixin\.qq\.com.*finder',
        r'szvideo\.weixin\.qq\.com',
        # 图片/缩略图域名
        r'mpvideo\.qpic\.cn',
        r'ugc\.qpic\.cn',
        r'puui\.qpic\.cn.*finder',
        # 国际版域名
        r'finder\.video\.wechat\.com',
        r'finder\.video\.qq\.com\.cn',
        # 动态/短视频域名
        r'wxsnsdy\.video\.qq\.com',
        r'wxsnsdythumb\.video\.qq\.com',
        r'wxsnsdy\.tc\.qq\.com',
        r'wxsnsdythumb\.tc\.qq\.com',
        # 直播相关
        r'finder\.live\.qq\.com',
        r'finderlivevideo\.video\.qq\.com',
        # 其他
        r'vweixinf\.tc\.qq\.com',
        r'finderim\.qq\.com',
        # 小程序视频（关键！）
        r'wxapp\.tc\.qq\.com',
        r'stodownload\.wxapp\.tc\.qq\.com',
        # 腾讯视频 CDN（需要更精确的匹配）
        r'.*\.tc\.qq\.com.*stodownload',
        r'finder.*\.video\.qq\.com',
    ]
    
    # 视频文件扩展名模式（扩展版）
    VIDEO_EXTENSIONS = ['.mp4', '.m4v', '.mov', '.webm', '.flv', '.m3u8', '.ts']
    
    # 视频 Content-Type 列表（扩展版）
    VIDEO_CONTENT_TYPES = [
        'video/',
        'application/octet-stream',
        'application/mp4',
        # HLS 相关
        'application/vnd.apple.mpegurl',
        'application/x-mpegurl',
        'video/mp2t',
        'audio/mpegurl',
        'audio/x-mpegurl',
        # DASH 相关
        'application/dash+xml',
    ]
    
    # 编译正则表达式以提高性能
    _compiled_patterns = None
    
    @classmethod
    def _get_compiled_patterns(cls):
        """获取编译后的正则表达式"""
        if cls._compiled_patterns is None:
            cls._compiled_patterns = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in cls.VIDEO_PATTERNS
            ]
        return cls._compiled_patterns
    
    @staticmethod
    def is_channels_video_url(url: str) -> bool:
        """检查 URL 是否为视频号视频
        
        Args:
            url: 要检查的 URL
            
        Returns:
            如果是视频号视频 URL 返回 True，否则返回 False
        """
        if not url or not isinstance(url, str):
            return False
        
        url_lower = url.lower()
        
        # 只接受 HTTP/HTTPS 协议
        if not (url_lower.startswith('http://') or url_lower.startswith('https://')):
            return False
        
        # 检查是否匹配视频号域名模式
        for pattern in PlatformDetector._get_compiled_patterns():
            if pattern.search(url_lower):
                return True
        
        return False
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """从 URL 提取视频 ID
        
        Args:
            url: 视频 URL
            
        Returns:
            视频 ID，如果无法提取则返回 None
        """
        if not url or not isinstance(url, str):
            return None
        
        try:
            parsed = urlparse(url)
            
            # 尝试从查询参数中提取
            query_params = parse_qs(parsed.query)
            
            # 常见的视频 ID 参数名（优先使用 encfilekey，这是视频号的唯一标识）
            id_params = ['encfilekey', 'filekey', 'vid', 'video_id', 'objectId', 'feedId', 'id']
            for param in id_params:
                if param in query_params:
                    value = query_params[param][0]
                    # 对于 encfilekey，使用前16个字符作为ID（太长会导致显示问题）
                    if param == 'encfilekey' and len(value) > 16:
                        return hashlib.md5(value.encode()).hexdigest()[:16]
                    return value
            
            # 尝试从路径中提取
            path_parts = parsed.path.strip('/').split('/')
            for part in path_parts:
                # 视频 ID 通常是较长的字母数字字符串
                if len(part) >= 10 and part.isalnum():
                    return part
            
            # 如果无法提取，使用 URL 的哈希作为唯一标识
            return hashlib.md5(url.encode()).hexdigest()[:16]
            
        except Exception:
            return None
    
    @staticmethod
    def extract_metadata_from_response(
        url: str, 
        headers: Dict[str, str], 
        content: bytes
    ) -> Optional[VideoMetadata]:
        """从响应中提取视频元数据
        
        Args:
            url: 请求 URL
            headers: 响应头
            content: 响应内容（可能为空或部分内容）
            
        Returns:
            VideoMetadata 对象，如果无法提取则返回 None
        """
        if not url:
            return None
        
        metadata = VideoMetadata()
        
        try:
            # 从 Content-Length 获取文件大小
            content_length = headers.get('Content-Length') or headers.get('content-length')
            if content_length:
                try:
                    metadata.filesize = int(content_length)
                except ValueError:
                    pass
            
            # 从 Content-Disposition 获取文件名/标题
            content_disp = headers.get('Content-Disposition') or headers.get('content-disposition')
            if content_disp:
                # 尝试提取 filename
                match = re.search(r'filename[*]?=["\']?([^"\';\n]+)', content_disp)
                if match:
                    filename = match.group(1)
                    # 移除扩展名作为标题
                    for ext in PlatformDetector.VIDEO_EXTENSIONS:
                        if filename.lower().endswith(ext):
                            metadata.title = filename[:-len(ext)]
                            break
                    else:
                        metadata.title = filename
            
            # 从 URL 参数中提取可能的元数据
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # 尝试获取分辨率
            for param in ['resolution', 'quality', 'fmt']:
                if param in query_params:
                    metadata.resolution = query_params[param][0]
                    break
            
            # 尝试获取时长
            for param in ['duration', 'dur', 'len']:
                if param in query_params:
                    try:
                        metadata.duration = int(query_params[param][0])
                    except ValueError:
                        pass
                    break
            
            return metadata
            
        except Exception:
            return None
    
    @staticmethod
    def is_video_content_type(content_type: str) -> bool:
        """检查 Content-Type 是否为视频类型（扩展版）
        
        支持常规视频类型、HLS 和 DASH 格式。
        
        Args:
            content_type: HTTP Content-Type 头
            
        Returns:
            如果是视频类型返回 True
        """
        if not content_type:
            return False
        
        content_type_lower = content_type.lower()
        
        return any(vt in content_type_lower for vt in PlatformDetector.VIDEO_CONTENT_TYPES)
    
    @staticmethod
    def is_video_url_by_extension(url: str) -> bool:
        """通过 URL 扩展名判断是否为视频
        
        Args:
            url: 要检查的 URL
            
        Returns:
            如果 URL 以视频扩展名结尾返回 True
        """
        if not url or not isinstance(url, str):
            return False
        
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # 移除查询参数后检查扩展名
            for ext in PlatformDetector.VIDEO_EXTENSIONS:
                if path.endswith(ext):
                    return True
            
            return False
        except Exception:
            return False
    
    @staticmethod
    def is_hls_content(url: str, content_type: str = "") -> bool:
        """检查是否为 HLS 内容
        
        Args:
            url: 请求 URL
            content_type: Content-Type 头（可选）
            
        Returns:
            如果是 HLS 内容返回 True
        """
        # 检查 URL 扩展名
        if url:
            url_lower = url.lower()
            parsed = urlparse(url_lower)
            path = parsed.path
            if path.endswith('.m3u8') or path.endswith('.ts'):
                return True
        
        # 检查 Content-Type
        if content_type:
            ct_lower = content_type.lower()
            hls_types = [
                'application/vnd.apple.mpegurl',
                'application/x-mpegurl',
                'audio/mpegurl',
                'audio/x-mpegurl',
                'video/mp2t',
            ]
            if any(ht in ct_lower for ht in hls_types):
                return True
        
        return False
    
    @staticmethod
    def is_dash_content(url: str, content_type: str = "") -> bool:
        """检查是否为 DASH 内容
        
        Args:
            url: 请求 URL
            content_type: Content-Type 头（可选）
            
        Returns:
            如果是 DASH 内容返回 True
        """
        # 检查 URL 扩展名
        if url:
            url_lower = url.lower()
            parsed = urlparse(url_lower)
            path = parsed.path
            if path.endswith('.mpd'):
                return True
        
        # 检查 Content-Type
        if content_type:
            if 'application/dash+xml' in content_type.lower():
                return True
        
        return False
    
    @staticmethod
    def extract_decryption_key(url: str) -> Optional[str]:
        """从 URL 参数中提取解密密钥
        
        Args:
            url: 视频 URL
            
        Returns:
            解密密钥字符串，如果没有则返回 None
        """
        if not url:
            return None
        
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # 常见的密钥参数名
            key_params = ['key', 'decryptkey', 'dk', 'enckey']
            for param in key_params:
                if param in query_params:
                    return query_params[param][0]
            
            return None
            
        except Exception:
            return None
