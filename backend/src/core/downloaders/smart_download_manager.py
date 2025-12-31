"""
智能下载管理器
实现自动回退策略：默认使用通用下载器，认证错误时回退到专用下载器
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .downloader_factory import DownloaderFactory
from .error_classifier import is_auth_required_error, is_non_retryable_error, classify_error
from .cookie_manager import (
    get_cookie_path_for_platform,
    has_cookie_for_platform,
    create_friendly_cookie_error,
    get_platform_display_name,
)

logger = logging.getLogger(__name__)


class SmartDownloadManager:
    """
    智能下载管理器
    
    实现自动回退策略：
    1. 默认使用通用下载器（无 Cookie）
    2. 认证错误时自动回退到专用下载器（带 Cookie）
    3. 非认证错误直接报错，不浪费时间重试
    """
    
    def __init__(self, output_dir: str = "./data/downloads"):
        self.output_dir = output_dir
    
    async def get_info_with_fallback(self, url: str) -> Dict[str, Any]:
        """
        获取视频信息，支持智能回退
        
        Args:
            url: 视频链接
            
        Returns:
            视频信息字典，包含额外字段：
            - downloader_used: 使用的下载器名称
            - fallback_used: 是否使用了回退
            - fallback_reason: 回退原因（如果有）
        """
        platform = DownloaderFactory.detect_platform(url)
        logger.info(f"[SmartDownload] Getting info for URL: {url}, platform: {platform}")
        
        # Step 1: 尝试通用下载器（无 Cookie）
        generic = DownloaderFactory.get_generic_downloader(self.output_dir)
        generic_error = None
        
        try:
            logger.info(f"[SmartDownload] Trying GenericDownloader (no cookie)...")
            result = await generic.get_video_info(url)
            
            # 成功，添加元信息
            result['downloader_used'] = 'generic'
            result['fallback_used'] = False
            result['fallback_reason'] = None
            logger.info(f"[SmartDownload] GenericDownloader succeeded")
            return result
            
        except Exception as e:
            generic_error = e
            logger.warning(f"[SmartDownload] GenericDownloader failed: {str(e)[:200]}")
        
        # Step 2: 判断是否需要回退
        error_msg = str(generic_error)
        error_type = classify_error(error_msg, platform)
        
        if error_type == 'non_retryable':
            # 不可重试错误，直接报错
            logger.info(f"[SmartDownload] Non-retryable error, not falling back")
            raise generic_error
        
        if error_type != 'auth_required':
            # 未知错误，尝试回退（可能是网络问题等）
            logger.info(f"[SmartDownload] Unknown error type, attempting fallback anyway")
        
        # Step 3: 先尝试专用下载器（即使没有 Cookie，专用下载器可能有更好的处理逻辑）
        # 例如 YouTube 专用下载器有 player_client 回退机制
        specialized = DownloaderFactory.get_specialized_downloader(url, self.output_dir)
        
        try:
            logger.info(f"[SmartDownload] Trying {specialized.platform_name} downloader...")
            result = await specialized.get_video_info(url)
            
            # 成功，添加元信息
            result['downloader_used'] = specialized.platform_name
            result['fallback_used'] = True
            result['fallback_reason'] = error_msg[:200]  # 截断过长的错误信息
            logger.info(f"[SmartDownload] Specialized downloader succeeded after fallback")
            return result
            
        except Exception as e:
            specialized_error = e
            logger.warning(f"[SmartDownload] Specialized downloader also failed: {str(e)[:200]}")
        
        # Step 4: 专用下载器也失败，检查是否需要 Cookie
        specialized_error_msg = str(specialized_error)
        
        # 如果是认证错误且没有配置 Cookie，提示用户配置
        if error_type == 'auth_required' or classify_error(specialized_error_msg, platform) == 'auth_required':
            if not has_cookie_for_platform(platform):
                friendly_error = create_friendly_cookie_error(platform, specialized_error_msg)
                logger.info(f"[SmartDownload] Cookie not configured for {platform}, auth required")
                raise Exception(friendly_error)
        
        # 返回综合错误
        logger.error(f"[SmartDownload] All downloaders failed")
        raise Exception(
            f"下载失败。\n\n"
            f"🔹 通用下载器错误:\n{str(generic_error)[:300]}\n\n"
            f"🔹 专用下载器错误:\n{str(specialized_error)[:300]}"
        )
    
    async def download_with_fallback(
        self,
        url: str,
        quality: str = "best",
        output_path: Optional[str] = None,
        format_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        下载视频，支持智能回退
        
        Args:
            url: 视频链接
            quality: 画质选择
            output_path: 输出路径
            format_id: 格式ID
            progress_callback: 进度回调
            task_id: 任务ID
            **kwargs: 其他参数
            
        Returns:
            下载结果字典，包含额外字段：
            - downloader_used: 使用的下载器名称
            - fallback_used: 是否使用了回退
            - fallback_reason: 回退原因（如果有）
        """
        platform = DownloaderFactory.detect_platform(url)
        logger.info(f"[SmartDownload] Downloading URL: {url}, platform: {platform}, quality: {quality}")
        
        # Step 1: 尝试通用下载器（无 Cookie）
        generic = DownloaderFactory.get_generic_downloader(self.output_dir)
        generic_error = None
        
        try:
            logger.info(f"[SmartDownload] Trying GenericDownloader (no cookie)...")
            result = await generic.download_video(
                url=url,
                quality=quality,
                output_path=output_path,
                format_id=format_id,
                progress_callback=progress_callback,
                task_id=task_id,
                **kwargs
            )
            
            # 成功，添加元信息
            result['downloader_used'] = 'generic'
            result['fallback_used'] = False
            result['fallback_reason'] = None
            logger.info(f"[SmartDownload] GenericDownloader download succeeded")
            return result
            
        except Exception as e:
            generic_error = e
            logger.warning(f"[SmartDownload] GenericDownloader download failed: {str(e)[:200]}")
        
        # Step 2: 判断是否需要回退
        error_msg = str(generic_error)
        error_type = classify_error(error_msg, platform)
        
        if error_type == 'non_retryable':
            # 不可重试错误，直接报错
            logger.info(f"[SmartDownload] Non-retryable error, not falling back")
            if progress_callback and task_id:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(generic_error)
                })
            raise generic_error
        
        if error_type != 'auth_required':
            # 未知错误，尝试回退（可能是网络问题等）
            logger.info(f"[SmartDownload] Unknown error type, attempting fallback anyway")
        
        # Step 3: 先尝试专用下载器（即使没有 Cookie，专用下载器可能有更好的处理逻辑）
        # 例如 YouTube 专用下载器有 player_client 回退机制，可以处理公开视频
        specialized = DownloaderFactory.get_specialized_downloader(url, self.output_dir)
        
        # 通知用户正在回退
        if progress_callback and task_id:
            platform_name = get_platform_display_name(platform)
            await progress_callback({
                'task_id': task_id,
                'status': 'fallback',
                'message': f'正在使用 {platform_name} 专用下载器重试...'
            })
        
        try:
            logger.info(f"[SmartDownload] Trying {specialized.platform_name} downloader...")
            result = await specialized.download_video(
                url=url,
                quality=quality,
                output_path=output_path,
                format_id=format_id,
                progress_callback=progress_callback,
                task_id=task_id,
                **kwargs
            )
            
            # 成功，添加元信息
            result['downloader_used'] = specialized.platform_name
            result['fallback_used'] = True
            result['fallback_reason'] = error_msg[:200]
            logger.info(f"[SmartDownload] Specialized downloader download succeeded after fallback")
            return result
            
        except Exception as e:
            specialized_error = e
            logger.warning(f"[SmartDownload] Specialized downloader also failed: {str(e)[:200]}")
        
        # Step 4: 专用下载器也失败，检查是否需要 Cookie
        specialized_error_msg = str(specialized_error)
        
        # 如果是认证错误且没有配置 Cookie，提示用户配置
        if error_type == 'auth_required' or classify_error(specialized_error_msg, platform) == 'auth_required':
            if not has_cookie_for_platform(platform):
                friendly_error = create_friendly_cookie_error(platform, specialized_error_msg)
                logger.info(f"[SmartDownload] Cookie not configured for {platform}, auth required")
                if progress_callback and task_id:
                    await progress_callback({
                        'task_id': task_id,
                        'status': 'error',
                        'error': friendly_error
                    })
                raise Exception(friendly_error)
        
        # 返回综合错误
        logger.error(f"[SmartDownload] All downloaders failed")
        combined_error = (
            f"下载失败。\n\n"
            f"🔹 通用下载器错误:\n{str(generic_error)[:300]}\n\n"
            f"🔹 专用下载器错误:\n{str(specialized_error)[:300]}"
        )
        if progress_callback and task_id:
            await progress_callback({
                'task_id': task_id,
                'status': 'error',
                'error': combined_error
            })
        raise Exception(combined_error)


# 全局单例
_smart_manager: Optional[SmartDownloadManager] = None


def get_smart_download_manager(output_dir: str = "./data/downloads") -> SmartDownloadManager:
    """获取智能下载管理器单例"""
    global _smart_manager
    if _smart_manager is None:
        _smart_manager = SmartDownloadManager(output_dir)
    return _smart_manager
