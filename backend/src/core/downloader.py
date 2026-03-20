"""
视频下载器核心模块
使用智能回退策略的下载器架构
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime

# 导入智能下载管理器
from .downloaders.smart_download_manager import SmartDownloadManager

logger = logging.getLogger(__name__)


class Downloader:
    """
    视频下载器核心类
    使用智能回退策略：默认通用下载器，认证错误时回退到专用下载器
    """

    def __init__(self, output_dir: str = None):
        # 如果没有指定输出目录，使用系统默认下载路径
        if output_dir is None:
            from src.core.config_manager import get_default_download_path
            output_dir = get_default_download_path()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.active_downloads: Dict[str, Any] = {}
        # 使用智能下载管理器
        self._smart_manager = SmartDownloadManager(str(self.output_dir))

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        获取视频信息（不下载）
        使用智能回退策略：
        1. 先尝试通用下载器（无 Cookie）
        2. 认证错误时回退到专用下载器（带 Cookie）

        Args:
            url: 视频链接

        Returns:
            视频信息字典，包含：
            - downloader_used: 使用的下载器名称
            - fallback_used: 是否使用了回退
            - fallback_reason: 回退原因（如果有）
        """
        logger.info(f"Getting video info for: {url}")
        return await self._smart_manager.get_info_with_fallback(url)

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
        使用智能回退策略：
        1. 先尝试通用下载器（无 Cookie）
        2. 认证错误时回退到专用下载器（带 Cookie）

        Args:
            url: 视频链接
            quality: 质量选择 (best, 1080p, 720p, 480p, etc.)
            output_path: 输出路径
            format_id: 指定格式ID
            progress_callback: 进度回调函数
            task_id: 任务ID

        Returns:
            下载结果信息，包含：
            - downloader_used: 使用的下载器名称
            - fallback_used: 是否使用了回退
            - fallback_reason: 回退原因（如果有）
        """
        # 如果指定了输出路径，更新智能管理器的输出目录
        actual_output_dir = output_path or str(self.output_dir)

        # 复用智能管理器实例，仅在输出目录不同时更新
        if self._smart_manager.output_dir != actual_output_dir:
            self._smart_manager.output_dir = actual_output_dir

        logger.info(f"Downloading video: {url}, quality: {quality}")
        return await self._smart_manager.download_with_fallback(
            url=url,
            quality=quality,
            output_path=actual_output_dir,
            format_id=format_id,
            progress_callback=progress_callback,
            task_id=task_id
        )
