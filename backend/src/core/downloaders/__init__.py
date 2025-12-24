"""
多平台视频下载器模块
支持 YouTube, Bilibili, 抖音/TikTok 等多个平台
✨ 新增：视频信息缓存、抖音专用下载器
"""
from .base_downloader import BaseDownloader
from .downloader_factory import DownloaderFactory
from .cache_manager import VideoInfoCache, get_cache
from .youtube_downloader import YoutubeDownloader
from .bilibili_downloader import BilibiliDownloader
from .douyin_downloader import DouyinDownloader
from .generic_downloader import GenericDownloader

__all__ = [
    'BaseDownloader',
    'DownloaderFactory',
    'VideoInfoCache',
    'get_cache',
    'YoutubeDownloader',
    'BilibiliDownloader',
    'DouyinDownloader',
    'GenericDownloader',
]
