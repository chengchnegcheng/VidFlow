"""
多平台视频下载器模块
支持 YouTube, Bilibili, 抖音/TikTok 等多个平台
✨ 新增：智能回退策略、视频信息缓存、抖音专用下载器
"""
from .base_downloader import BaseDownloader
from .downloader_factory import DownloaderFactory
from .cache_manager import VideoInfoCache, get_cache
from .youtube_downloader import YoutubeDownloader
from .bilibili_downloader import BilibiliDownloader
from .douyin_downloader import DouyinDownloader
from .generic_downloader import GenericDownloader
from .smart_download_manager import SmartDownloadManager, get_smart_download_manager
from .error_classifier import is_auth_required_error, is_non_retryable_error, classify_error
from .cookie_manager import (
    get_cookie_path_for_platform,
    has_cookie_for_platform,
    create_friendly_cookie_error,
    get_platform_display_name,
    PLATFORM_COOKIE_MAP,
)

__all__ = [
    'BaseDownloader',
    'DownloaderFactory',
    'VideoInfoCache',
    'get_cache',
    'YoutubeDownloader',
    'BilibiliDownloader',
    'DouyinDownloader',
    'GenericDownloader',
    # 智能回退相关
    'SmartDownloadManager',
    'get_smart_download_manager',
    'is_auth_required_error',
    'is_non_retryable_error',
    'classify_error',
    'get_cookie_path_for_platform',
    'has_cookie_for_platform',
    'create_friendly_cookie_error',
    'get_platform_display_name',
    'PLATFORM_COOKIE_MAP',
]
