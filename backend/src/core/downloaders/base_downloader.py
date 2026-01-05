"""
基础下载器抽象类
定义所有下载器的通用接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import logging
import re
import os

logger = logging.getLogger(__name__)


def _validate_safe_path(base_dir: Path, target_path: Path) -> Path:
    base_abs = base_dir.resolve()
    target_abs = target_path.resolve()

    try:
        target_abs.relative_to(base_abs)
    except ValueError as e:
        raise ValueError(
            f"Path validation failed: '{target_path}' is outside base directory '{base_dir}'"
        ) from e

    return target_abs


def _sanitize_filename(filename: str, max_length: int = 200) -> str:
    name = str(filename or "")
    name = name.replace('/', '_').replace('\\', '_')
    name = name.replace('..', '_')
    name = re.sub(r'[<>:"|?*]', '', name)
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    name = name.strip()

    if len(name) > max_length:
        stem, ext = os.path.splitext(name)
        name = stem[:max(1, max_length - len(ext))] + ext

    if not name:
        name = 'video'

    return name


class BaseDownloader(ABC):
    """下载器基类，定义统一接口"""
    
    def __init__(self, output_dir: str = None, enable_cache: bool = True):
        # 如果没有指定输出目录，使用系统默认下载路径
        if output_dir is None:
            from src.core.config_manager import get_default_download_path
            output_dir = get_default_download_path()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.platform_name = "generic"
        self.enable_cache = enable_cache
        self._cache = None  # 延迟加载缓存
    
    @abstractmethod
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        获取视频信息（不下载）
        
        Args:
            url: 视频链接
            
        Returns:
            视频信息字典，包含：
            - title: 标题
            - duration: 时长（秒）
            - thumbnail: 缩略图URL
            - description: 描述
            - uploader: 上传者
            - formats: 可用格式列表
        """
        pass
    
    @abstractmethod
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
        
        Args:
            url: 视频链接
            quality: 质量选择
            output_path: 输出路径
            format_id: 指定格式ID
            progress_callback: 进度回调函数
            task_id: 任务ID
            
        Returns:
            下载结果信息
        """
        pass
    
    @staticmethod
    def supports_url(url: str) -> bool:
        """
        检查此下载器是否支持该URL
        
        Args:
            url: 视频链接
            
        Returns:
            是否支持
        """
        return False
    
    def _get_format_selector(self, quality: str, format_id: Optional[str] = None) -> str:
        """获取格式选择器字符串
        
        优先选择 H.264 (avc1) 编码，确保在手机和微信等应用中兼容播放
        """
        if format_id:
            fid = str(format_id).strip().lower()
            if fid not in ('mp4', 'mkv', 'webm', 'mp3'):
                return format_id

        q = (quality or 'best').strip().lower()
        if re.fullmatch(r'\d{3,4}', q):
            q = f"{q}p"

        # 改进的格式选择器 - 优先 H.264 编码确保兼容性
        # vcodec^=avc 表示优先选择 H.264 编码（avc1）
        # 回退策略：H.264 -> 任意编码 -> best
        quality_map = {
            # best: 优先 H.264 编码的最佳视频+AAC音频，确保手机兼容
            'best': 'bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo[vcodec^=avc]+bestaudio/bestvideo+bestaudio/best',
            # 指定分辨率: 优先 H.264 编码
            '2160p': 'bestvideo[height<=2160][vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo[height<=2160][vcodec^=avc]+bestaudio/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
            '1440p': 'bestvideo[height<=1440][vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo[height<=1440][vcodec^=avc]+bestaudio/bestvideo[height<=1440]+bestaudio/best[height<=1440]/best',
            '1080p': 'bestvideo[height<=1080][vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo[height<=1080][vcodec^=avc]+bestaudio/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            '720p': 'bestvideo[height<=720][vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo[height<=720][vcodec^=avc]+bestaudio/bestvideo[height<=720]+bestaudio/best[height<=720]/best',
            '480p': 'bestvideo[height<=480][vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo[height<=480][vcodec^=avc]+bestaudio/bestvideo[height<=480]+bestaudio/best[height<=480]/best',
            '360p': 'bestvideo[height<=360][vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo[height<=360][vcodec^=avc]+bestaudio/bestvideo[height<=360]+bestaudio/best[height<=360]/best',
            # 仅音频
            'audio': 'bestaudio[acodec^=mp4a]/bestaudio/best',
        }

        return quality_map.get(q, quality_map['best'])

    def _get_base_ydl_opts(self) -> dict:
        return {
            'continuedl': True,
            'nopart': False,
            'overwrites': False,
            'noprogress': False,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': False,
        }
    
    def _extract_formats(self, info: Dict) -> list:
        """从视频信息中提取格式列表"""
        formats = []
        
        if 'formats' in info:
            for fmt in info['formats']:
                format_info = {
                    'format_id': fmt.get('format_id', ''),
                    'ext': fmt.get('ext', ''),
                    'quality': fmt.get('format_note', ''),
                    'filesize': fmt.get('filesize', 0),
                    'vcodec': fmt.get('vcodec', ''),
                    'acodec': fmt.get('acodec', ''),
                    'height': fmt.get('height', 0),
                    'width': fmt.get('width', 0),
                    'fps': fmt.get('fps', 0),
                }
                formats.append(format_info)
        
        return formats
    
    def _get_cache(self):
        """获取缓存实例（延迟加载）"""
        if self._cache is None and self.enable_cache:
            try:
                from .cache_manager import get_cache
                self._cache = get_cache()
            except Exception as e:
                logger.warning(f"Failed to initialize cache: {e}")
                self.enable_cache = False
        return self._cache
    
    def _get_cached_info(self, url: str) -> Optional[Dict[str, Any]]:
        """从缓存获取视频信息"""
        if not self.enable_cache:
            return None
        
        cache = self._get_cache()
        if cache:
            return cache.get(url)
        return None
    
    def _cache_info(self, url: str, info: Dict[str, Any]):
        """缓存视频信息"""
        if not self.enable_cache:
            return
        
        cache = self._get_cache()
        if cache:
            cache.set(url, info)
    
    def _sanitize_filename(self, filename: str, max_length: int = 200) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            max_length: 最大长度
            
        Returns:
            清理后的文件名
        """
        return _sanitize_filename(filename, max_length=max_length)
