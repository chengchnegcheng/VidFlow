"""
HTTP 流量监控器

监控 HTTP 流量，提取视频号视频 URL 和 encfilekey
"""

import logging
import re
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse, parse_qs
from mitmproxy import http
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.options import Options

logger = logging.getLogger(__name__)


class HTTPMonitor:
    """HTTP 流量监控器"""
    
    # 视频号域名模式
    VIDEO_DOMAINS = [
        'wxapp.tc.qq.com',
        'finder.video.qq.com',
        'findermp.video.qq.com',
    ]
    
    # URL 模式
    URL_PATTERNS = [
        r'/\d+/\d+/stodownload',  # 标准下载 URL
        r'/finder/',  # finder 相关
    ]
    
    def __init__(self, on_video_detected: Optional[Callable] = None):
        """初始化
        
        Args:
            on_video_detected: 检测到视频时的回调函数
        """
        self.on_video_detected = on_video_detected
        self.detected_videos = []
    
    def is_video_url(self, url: str) -> bool:
        """判断是否是视频 URL
        
        Args:
            url: URL
            
        Returns:
            是否是视频 URL
        """
        try:
            parsed = urlparse(url)
            
            # 检查域名
            if not any(domain in parsed.netloc for domain in self.VIDEO_DOMAINS):
                return False
            
            # 检查路径模式
            if not any(re.search(pattern, parsed.path) for pattern in self.URL_PATTERNS):
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"判断 URL 失败: {e}")
            return False
    
    def extract_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """从 URL 中提取视频信息
        
        Args:
            url: 视频 URL
            
        Returns:
            视频信息
        """
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # 提取 encfilekey（解密密钥）
            encfilekey = query_params.get('encfilekey', [None])[0]
            if not encfilekey:
                logger.warning(f"URL 中没有 encfilekey: {url}")
                return None
            
            # 提取其他参数
            bizid = query_params.get('bizid', [None])[0]
            idx = query_params.get('idx', [None])[0]
            
            video_info = {
                'url': url,
                'encfilekey': encfilekey,
                'bizid': bizid,
                'idx': idx,
                'domain': parsed.netloc,
            }
            
            logger.info(f"✅ 提取到视频信息:")
            logger.info(f"  URL: {url[:100]}...")
            logger.info(f"  encfilekey: {encfilekey[:50]}...")
            
            return video_info
            
        except Exception as e:
            logger.exception(f"提取视频信息失败: {e}")
            return None
    
    def process_request(self, flow: http.HTTPFlow):
        """处理 HTTP 请求
        
        Args:
            flow: HTTP 流
        """
        try:
            url = flow.request.pretty_url
            
            # 检查是否是视频 URL
            if self.is_video_url(url):
                logger.info(f"🎬 检测到视频号视频请求: {url[:100]}...")
                
                # 提取视频信息
                video_info = self.extract_video_info(url)
                
                if video_info:
                    self.detected_videos.append(video_info)
                    
                    # 触发回调
                    if self.on_video_detected:
                        self.on_video_detected(video_info)
                        
        except Exception as e:
            logger.debug(f"处理请求失败: {e}")
    
    def process_response(self, flow: http.HTTPFlow):
        """处理 HTTP 响应
        
        Args:
            flow: HTTP 流
        """
        try:
            # 可以在这里处理响应，例如检查 Content-Type
            if self.is_video_url(flow.request.pretty_url):
                content_type = flow.response.headers.get('Content-Type', '')
                content_length = flow.response.headers.get('Content-Length', '0')
                
                logger.info(f"  响应: Content-Type={content_type}, Size={content_length}")
                
        except Exception as e:
            logger.debug(f"处理响应失败: {e}")
    
    def get_detected_videos(self) -> list:
        """获取检测到的视频列表
        
        Returns:
            视频列表
        """
        return self.detected_videos
    
    def clear_detected_videos(self):
        """清空检测到的视频列表"""
        self.detected_videos = []


class HTTPMonitorAddon:
    """mitmproxy 插件"""
    
    def __init__(self, monitor: HTTPMonitor):
        """初始化
        
        Args:
            monitor: HTTP 监控器
        """
        self.monitor = monitor
    
    def request(self, flow: http.HTTPFlow):
        """处理请求"""
        self.monitor.process_request(flow)
    
    def response(self, flow: http.HTTPFlow):
        """处理响应"""
        self.monitor.process_response(flow)
