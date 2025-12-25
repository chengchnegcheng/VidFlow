"""
视频下载器核心模块
使用模块化的下载器架构
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime

# 导入下载器工厂
from .downloaders.downloader_factory import DownloaderFactory

logger = logging.getLogger(__name__)


class Downloader:
    """
    视频下载器核心类
    使用工厂模式自动选择合适的下载器
    """
    
    def __init__(self, output_dir: str = "./data/downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.active_downloads: Dict[str, Any] = {}
        
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        获取视频信息（不下载）
        优先使用通用下载器,失败后再尝试专用下载器

        Args:
            url: 视频链接

        Returns:
            视频信息字典
        """
        # 策略: 先尝试通用下载器(更稳定),失败后再使用专用下载器
        from .downloaders.generic_downloader import GenericDownloader

        # 第一次尝试: 使用通用下载器
        generic_downloader = GenericDownloader(str(self.output_dir))

        try:
            logger.info(f"Attempting to get video info with GenericDownloader for: {url}")
            info = await generic_downloader.get_video_info(url)
            logger.info("✅ GenericDownloader succeeded")
            return info
        except Exception as generic_error:
            logger.warning(f"GenericDownloader failed: {generic_error}")

            # 第二次尝试: 使用专用下载器
            platform = DownloaderFactory.detect_platform(url)

            # 如果平台是 youtube,尝试使用专用下载器
            if platform == 'youtube':
                try:
                    specialized_downloader = DownloaderFactory.get_downloader(url, str(self.output_dir))
                    logger.info(f"Retrying with specialized downloader: {specialized_downloader.__class__.__name__}")
                    info = await specialized_downloader.get_video_info(url)
                    logger.info("✅ Specialized downloader succeeded")
                    return info
                except Exception as specialized_error:
                    logger.error(f"Both downloaders failed. Generic error: {generic_error}, Specialized error: {specialized_error}")
                    # 抛出专用下载器的错误(通常更详细)
                    raise specialized_error
            else:
                # 非 YouTube,直接抛出通用下载器的错误
                raise generic_error
    
    async def download_video(
        self,
        url: str,
        quality: str = "best",
        output_path: Optional[str] = None,
        format_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        下载视频
        优先使用通用下载器,失败后再尝试专用下载器

        Args:
            url: 视频链接
            quality: 质量选择 (best, 1080p, 720p, 480p, etc.)
            output_path: 输出路径
            format_id: 指定格式ID
            progress_callback: 进度回调函数
            task_id: 任务ID

        Returns:
            下载结果信息
        """
        output_path = output_path or str(self.output_dir)

        # 策略: 先尝试通用下载器(更稳定),失败后再使用专用下载器
        from .downloaders.generic_downloader import GenericDownloader

        # 第一次尝试: 使用通用下载器
        generic_downloader = GenericDownloader(output_path)

        try:
            logger.info(f"Attempting to download with GenericDownloader for: {url}")
            result = await generic_downloader.download_video(
                url=url,
                quality=quality,
                output_path=output_path,
                format_id=format_id,
                progress_callback=progress_callback,
                task_id=task_id
            )
            logger.info("✅ GenericDownloader download succeeded")
            return result
        except Exception as generic_error:
            logger.warning(f"GenericDownloader download failed: {generic_error}")

            # 第二次尝试: 使用专用下载器
            platform = DownloaderFactory.detect_platform(url)

            # 如果平台是 youtube,尝试使用专用下载器
            if platform == 'youtube':
                try:
                    specialized_downloader = DownloaderFactory.get_downloader(url, output_path)
                    logger.info(f"Retrying download with specialized downloader: {specialized_downloader.__class__.__name__}")
                    result = await specialized_downloader.download_video(
                        url=url,
                        quality=quality,
                        output_path=output_path,
                        format_id=format_id,
                        progress_callback=progress_callback,
                        task_id=task_id
                    )
                    logger.info("✅ Specialized downloader download succeeded")
                    return result
                except Exception as specialized_error:
                    logger.error(f"Both downloaders failed. Generic error: {generic_error}, Specialized error: {specialized_error}")
                    if progress_callback and task_id:
                        await progress_callback({
                            'task_id': task_id,
                            'status': 'error',
                            'error': str(specialized_error)
                        })
                    # 抛出专用下载器的错误(通常更详细)
                    raise specialized_error
            else:
                # 非 YouTube,直接抛出通用下载器的错误
                if progress_callback and task_id:
                    await progress_callback({
                        'task_id': task_id,
                        'status': 'error',
                        'error': str(generic_error)
                    })
                raise generic_error
