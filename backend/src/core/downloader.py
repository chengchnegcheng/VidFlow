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
        自动选择合适的下载器
        
        Args:
            url: 视频链接
            
        Returns:
            视频信息字典
        """
        try:
            # 使用工厂获取合适的下载器
            downloader = DownloaderFactory.get_downloader(url, str(self.output_dir))
            platform = DownloaderFactory.detect_platform(url)
            
            logger.info(f"Using {downloader.__class__.__name__} for platform: {platform}")
            
            # 调用下载器的get_video_info方法
            return await downloader.get_video_info(url)
            
        except Exception as e:
            logger.error(f"Error extracting video info: {e}")
            raise
    
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
        自动选择合适的下载器
        
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
        try:
            output_path = output_path or str(self.output_dir)
            
            # 使用工厂获取合适的下载器
            downloader = DownloaderFactory.get_downloader(url, output_path)
            platform = DownloaderFactory.detect_platform(url)
            
            logger.info(f"Using {downloader.__class__.__name__} for platform: {platform}")
            
            # 调用下载器的download_video方法
            return await downloader.download_video(
                url=url,
                quality=quality,
                output_path=output_path,
                format_id=format_id,
                progress_callback=progress_callback,
                task_id=task_id
            )
            
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            if progress_callback and task_id:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(e)
                })
            raise
