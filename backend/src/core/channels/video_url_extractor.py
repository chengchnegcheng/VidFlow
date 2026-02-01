"""
视频URL提取器

智能识别和提取微信视频号视频URL。
支持多种URL模式匹配、排除过滤、视频ID提取和去重。

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

import re
import logging
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


@dataclass
class ExtractedVideo:
    """提取的视频信息
    
    Validates: Requirements 6.1, 6.4
    """
    url: str
    video_id: str
    source: str  # "http", "sni", "clash_api", "ip"
    domain: str
    is_encrypted: bool = False
    decryption_key: Optional[str] = None
    expires_at: Optional[datetime] = None
    quality: Optional[str] = None
    filesize: Optional[int] = None
    detected_at: datetime = field(default_factory=datetime.now)
    http_response: Optional[bytes] = None  # HTTP响应体，用于提取元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "url": self.url,
            "video_id": self.video_id,
            "source": self.source,
            "domain": self.domain,
            "is_encrypted": self.is_encrypted,
            "decryption_key": self.decryption_key,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "quality": self.quality,
            "filesize": self.filesize,
            "detected_at": self.detected_at.isoformat(),
        }


class VideoURLExtractor:
    """视频URL提取器
    
    智能识别和提取微信视频号视频URL。
    
    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
    """
    
    # 视频号URL模式（2025年更新）
    VIDEO_PATTERNS = [
        # 核心视频下载域名
        r'wxapp\.tc\.qq\.com',  # 所有wxapp.tc.qq.com都可能是视频
        r'finder\.video\.qq\.com',
        r'findermp\.video\.qq\.com',
        r'findervideodownload\.video\.qq\.com',
        # 微信渠道
        r'channels\.weixin\.qq\.com',
        r'szextshort\.weixin\.qq\.com',
        r'szvideo\.weixin\.qq\.com',
        # CDN域名
        r'vd\d*\.video\.qq\.com',
        r'.*\.tc\.qq\.com.*encfilekey',
        # 通用视频模式
        r'.*\.video\.qq\.com.*\.mp4',
        r'.*\.video\.qq\.com.*\.m3u8',
        # 视频号特定模式
        r'finder.*\.video\.qq\.com',
        r'mpvideo\.qpic\.cn',
    ]
    
    # 非视频请求模式（排除）
    EXCLUDE_PATTERNS = [
        # 图片
        r'\.jpg$', r'\.jpeg$', r'\.png$', r'\.gif$', r'\.webp$', r'\.ico$',
        r'\.jpg\?', r'\.jpeg\?', r'\.png\?', r'\.gif\?', r'\.webp\?',
        # API调用
        r'/cgi-bin/', r'/api/', r'/cgi/',
        # 静态资源
        r'\.js$', r'\.css$', r'\.js\?', r'\.css\?',
        r'\.woff', r'\.ttf', r'\.eot',
        # 追踪/日志
        r'beacon', r'report', r'log', r'trace', r'analytics',
        r'pingfore', r'pingback', r'stat',
        # 缩略图
        r'thumbnail', r'thumb', r'cover', r'poster',
        r'/\d+x\d+/', r'_\d+x\d+\.',  # 尺寸标识
        # 其他非视频
        r'\.xml$', r'\.json$', r'\.html$',
        r'manifest', r'playlist',  # 清单文件（非视频本身）
    ]
    
    # 视频ID提取模式
    VIDEO_ID_PATTERNS = [
        # encfilekey参数
        r'encfilekey=([a-zA-Z0-9_-]+)',
        # filekey参数
        r'filekey=([a-zA-Z0-9_-]+)',
        # vid参数
        r'vid=([a-zA-Z0-9_-]+)',
        # 路径中的ID
        r'/([a-zA-Z0-9]{32,})\.',
        r'/([a-zA-Z0-9_-]{20,})/[^/]+\.(mp4|m3u8)',
        # stodownload后的ID
        r'stodownload\?.*?m=([a-zA-Z0-9_-]+)',
    ]
    
    # 过期时间参数
    EXPIRE_PARAMS = ['e', 'expire', 'expires', 'exp', 't']
    
    def __init__(self):
        # 编译正则表达式以提高性能
        self._video_patterns = [re.compile(p, re.IGNORECASE) for p in self.VIDEO_PATTERNS]
        self._exclude_patterns = [re.compile(p, re.IGNORECASE) for p in self.EXCLUDE_PATTERNS]
        self._video_id_patterns = [re.compile(p, re.IGNORECASE) for p in self.VIDEO_ID_PATTERNS]
        
        # 已提取视频的ID集合（用于去重）
        self._extracted_ids: Set[str] = set()
    
    def is_video_url(self, url: str) -> bool:
        """判断是否为视频URL
        
        Property 8: Video URL Pattern Matching
        对于任何URL字符串，当且仅当URL匹配已知视频号模式
        且不匹配排除模式时返回True。
        
        Args:
            url: URL字符串
            
        Returns:
            是否为视频URL
        """
        if not url:
            return False
        
        # 首先检查排除模式
        if self.is_excluded(url):
            return False
        
        # 检查视频模式
        for pattern in self._video_patterns:
            if pattern.search(url):
                return True
        
        return False
    
    def is_excluded(self, url: str) -> bool:
        """判断是否应排除
        
        Args:
            url: URL字符串
            
        Returns:
            是否应排除
        """
        if not url:
            return True
        
        for pattern in self._exclude_patterns:
            if pattern.search(url):
                return True
        
        return False
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """提取视频ID
        
        Args:
            url: URL字符串
            
        Returns:
            视频ID，如果无法提取则返回None
        """
        if not url:
            return None
        
        # 尝试各种ID提取模式
        for pattern in self._video_id_patterns:
            match = pattern.search(url)
            if match:
                return match.group(1)
        
        # 如果无法提取，使用URL的哈希作为ID
        return self._generate_url_hash(url)
    
    def _generate_url_hash(self, url: str) -> str:
        """生成URL的哈希ID
        
        移除时间戳等变化参数后生成哈希。
        
        Args:
            url: URL字符串
            
        Returns:
            哈希ID
        """
        # 解析URL
        parsed = urlparse(url)
        
        # 移除可能变化的参数
        params = parse_qs(parsed.query)
        stable_params = {}
        
        for key, value in params.items():
            # 跳过时间戳和签名参数
            if key.lower() not in ['t', 'e', 'expire', 'expires', 'sign', 'signature', 'token', 'nonce']:
                stable_params[key] = value
        
        # 构建稳定的URL部分
        stable_url = f"{parsed.netloc}{parsed.path}"
        if stable_params:
            stable_url += "?" + "&".join(f"{k}={v[0]}" for k, v in sorted(stable_params.items()))
        
        # 生成哈希
        return hashlib.md5(stable_url.encode()).hexdigest()[:16]
    
    def extract_from_http(self, payload: bytes) -> Optional[ExtractedVideo]:
        """从HTTP请求中提取视频URL
        
        Args:
            payload: HTTP请求数据
            
        Returns:
            提取的视频信息，如果无法提取则返回None
        """
        if not payload:
            return None
        
        try:
            # 尝试解码
            text = payload.decode('utf-8', errors='ignore')
            
            # 查找URL
            url_pattern = re.compile(r'https?://[^\s\r\n"\'<>]+', re.IGNORECASE)
            urls = url_pattern.findall(text)
            
            for url in urls:
                if self.is_video_url(url):
                    return self._create_extracted_video(url, "http")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract from HTTP payload: {e}")
            return None
    
    def extract_from_sni(self, sni: str, dst_ip: str) -> Optional[ExtractedVideo]:
        """从SNI构建视频信息
        
        Args:
            sni: Server Name Indication
            dst_ip: 目标IP地址
            
        Returns:
            提取的视频信息，如果无法提取则返回None
        """
        if not sni:
            return None
        
        # 检查SNI是否匹配视频域名模式
        for pattern in self._video_patterns:
            if pattern.search(sni):
                # 构建基本URL
                url = f"https://{sni}/"
                video_id = self._generate_url_hash(f"{sni}:{dst_ip}")
                
                return ExtractedVideo(
                    url=url,
                    video_id=video_id,
                    source="sni",
                    domain=sni,
                    is_encrypted=False,
                )
        
        return None
    
    def extract_from_clash_connection(self, conn: Any) -> Optional[ExtractedVideo]:
        """从Clash连接信息提取
        
        Args:
            conn: Clash连接对象（ClashConnection）
            
        Returns:
            提取的视频信息，如果无法提取则返回None
        """
        if not conn:
            return None
        
        try:
            host = getattr(conn, 'host', None)
            if not host:
                return None
            
            # 检查host是否匹配视频域名模式
            for pattern in self._video_patterns:
                if pattern.search(host):
                    dst_ip = getattr(conn, 'dst_ip', '')
                    dst_port = getattr(conn, 'dst_port', 443)
                    
                    url = f"https://{host}/"
                    video_id = self._generate_url_hash(f"{host}:{dst_ip}:{dst_port}")
                    
                    return ExtractedVideo(
                        url=url,
                        video_id=video_id,
                        source="clash_api",
                        domain=host,
                        is_encrypted=False,
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract from Clash connection: {e}")
            return None
    
    def _create_extracted_video(self, url: str, source: str) -> ExtractedVideo:
        """创建ExtractedVideo对象
        
        Args:
            url: 视频URL
            source: 来源
            
        Returns:
            ExtractedVideo对象
        """
        parsed = urlparse(url)
        video_id = self.extract_video_id(url)
        
        # 检查是否加密
        is_encrypted = 'encfilekey' in url.lower() or 'enc' in parsed.path.lower()
        
        # 提取解密密钥
        decryption_key = None
        if is_encrypted:
            params = parse_qs(parsed.query)
            decryption_key = params.get('encfilekey', [None])[0]
        
        # 提取过期时间
        expires_at = self._extract_expiration(url)
        
        # 提取质量信息
        quality = self._extract_quality(url)
        
        return ExtractedVideo(
            url=url,
            video_id=video_id or self._generate_url_hash(url),
            source=source,
            domain=parsed.netloc,
            is_encrypted=is_encrypted,
            decryption_key=decryption_key,
            expires_at=expires_at,
            quality=quality,
        )
    
    def _extract_expiration(self, url: str) -> Optional[datetime]:
        """提取URL过期时间
        
        Args:
            url: URL字符串
            
        Returns:
            过期时间，如果无法提取则返回None
        """
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            for param in self.EXPIRE_PARAMS:
                if param in params:
                    value = params[param][0]
                    # 尝试解析为时间戳
                    try:
                        timestamp = int(value)
                        # 检查是否是合理的时间戳（秒或毫秒）
                        if timestamp > 1e12:  # 毫秒
                            timestamp = timestamp // 1000
                        if 1e9 < timestamp < 2e9:  # 合理的Unix时间戳范围
                            return datetime.fromtimestamp(timestamp)
                    except (ValueError, OSError):
                        pass
            
            return None
            
        except Exception:
            return None
    
    def _extract_quality(self, url: str) -> Optional[str]:
        """提取视频质量信息
        
        Args:
            url: URL字符串
            
        Returns:
            质量信息，如果无法提取则返回None
        """
        # 常见质量标识
        quality_patterns = [
            (r'1080[pP]', '1080p'),
            (r'720[pP]', '720p'),
            (r'480[pP]', '480p'),
            (r'360[pP]', '360p'),
            (r'4[kK]', '4K'),
            (r'2[kK]', '2K'),
            (r'hd', 'HD'),
            (r'sd', 'SD'),
        ]
        
        for pattern, quality in quality_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return quality
        
        return None
    
    def check_expiration(self, video: ExtractedVideo) -> bool:
        """检查视频URL是否过期
        
        Args:
            video: 视频信息
            
        Returns:
            是否已过期
        """
        if video.expires_at is None:
            return False
        
        return datetime.now() > video.expires_at
    
    def deduplicate(self, videos: List[ExtractedVideo]) -> List[ExtractedVideo]:
        """基于video_id去重
        
        Property 9: Video Deduplication by ID
        对于任何视频序列，去重后的列表中不应有两个视频具有相同的video_id。
        保留每个video_id的第一次出现。
        
        Args:
            videos: 视频列表
            
        Returns:
            去重后的视频列表
        """
        if not videos:
            return []
        
        seen_ids: Set[str] = set()
        result: List[ExtractedVideo] = []
        
        for video in videos:
            if video.video_id not in seen_ids:
                seen_ids.add(video.video_id)
                result.append(video)
        
        return result
    
    def extract_and_deduplicate(self, url: str, source: str = "http") -> Optional[ExtractedVideo]:
        """提取视频并去重
        
        如果视频ID已存在，返回None。
        
        Args:
            url: URL字符串
            source: 来源
            
        Returns:
            提取的视频信息，如果已存在或无法提取则返回None
        """
        if not self.is_video_url(url):
            return None
        
        video = self._create_extracted_video(url, source)
        
        # 检查是否已存在
        if video.video_id in self._extracted_ids:
            return None
        
        self._extracted_ids.add(video.video_id)
        return video
    
    def clear_extracted_ids(self) -> None:
        """清除已提取的视频ID集合"""
        self._extracted_ids.clear()
    
    def get_extracted_count(self) -> int:
        """获取已提取的视频数量"""
        return len(self._extracted_ids)
