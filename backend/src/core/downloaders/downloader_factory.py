"""
下载器工厂
根据URL自动选择合适的下载器
"""
import logging
from typing import Optional
from .base_downloader import BaseDownloader
from .youtube_downloader import YoutubeDownloader
from .bilibili_downloader import BilibiliDownloader
from .douyin_downloader import DouyinDownloader
from .generic_downloader import GenericDownloader

logger = logging.getLogger(__name__)


class DownloaderFactory:
    """下载器工厂类"""
    
    # 注册所有可用的下载器（按优先级排序）
    _downloaders = [
        DouyinDownloader,      # 抖音/TikTok
        YoutubeDownloader,     # YouTube
        BilibiliDownloader,    # Bilibili
        # 添加更多专用下载器
    ]
    
    @classmethod
    def get_downloader(cls, url: str, output_dir: str = "./data/downloads") -> BaseDownloader:
        """
        根据URL获取合适的下载器
        
        Args:
            url: 视频链接
            output_dir: 输出目录
            
        Returns:
            合适的下载器实例
        """
        # 遍历所有下载器，找到支持该URL的
        for downloader_class in cls._downloaders:
            if downloader_class.supports_url(url):
                logger.info(f"Using {downloader_class.__name__} for URL: {url}")
                return downloader_class(output_dir)
        
        # 如果没有专用下载器，使用通用下载器
        logger.info(f"Using GenericDownloader for URL: {url}")
        return GenericDownloader(output_dir)
    
    @classmethod
    def register_downloader(cls, downloader_class: type):
        """
        注册新的下载器类
        
        Args:
            downloader_class: 下载器类（必须继承自BaseDownloader）
        """
        if not issubclass(downloader_class, BaseDownloader):
            raise TypeError("Downloader must inherit from BaseDownloader")
        
        if downloader_class not in cls._downloaders:
            cls._downloaders.insert(0, downloader_class)  # 插入到前面，优先使用
            logger.info(f"Registered downloader: {downloader_class.__name__}")
    
    @classmethod
    def detect_platform(cls, url: str) -> str:
        """
        检测URL对应的平台

        Args:
            url: 视频链接

        Returns:
            平台名称
        """
        url_lower = url.lower()

        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'bilibili.com' in url_lower or 'b23.tv' in url_lower:
            return 'bilibili'
        # ✅ 先检查 TikTok，再检查 Douyin（避免误匹配）
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'douyin.com' in url_lower or 'v.douyin.com' in url_lower:
            return 'douyin'
        elif 'weixin' in url_lower or 'qq.com/channels' in url_lower:
            return 'weixin'
        elif 'xiaohongshu.com' in url_lower or 'xhslink.com' in url_lower:
            return 'xiaohongshu'
        elif 'v.qq.com' in url_lower:
            return 'tencent'
        elif 'youku.com' in url_lower:
            return 'youku'
        elif 'iqiyi.com' in url_lower:
            return 'iqiyi'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'twitter'
        elif 'instagram.com' in url_lower:
            return 'instagram'
        elif 'facebook.com' in url_lower:
            return 'facebook'
        else:
            return 'generic'
