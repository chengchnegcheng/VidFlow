"""
Bilibili 专用下载器
针对 B站 进行优化，支持cookie登录
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import yt_dlp
from src.core.tool_manager import get_tool_manager
from src.core.cookie_storage import cookiefile_for_ytdlp
from .base_downloader import BaseDownloader

logger = logging.getLogger(__name__)


class BilibiliDownloader(BaseDownloader):
    """Bilibili 专用下载器"""
    
    def __init__(self, output_dir: str = "./data/downloads"):
        super().__init__(output_dir)
        self.platform_name = "bilibili"
    
    @staticmethod
    def supports_url(url: str) -> bool:
        """检查是否支持该URL"""
        url_lower = url.lower()
        return 'bilibili.com' in url_lower or 'b23.tv' in url_lower
    
    def _get_bilibili_cookie_path(self) -> Optional[Path]:
        """
        获取 Bilibili Cookie 文件路径

        Returns:
            Cookie 文件路径，如果不存在则返回 None
        """
        base_dir = Path(__file__).parent.parent.parent.parent
        cookie_dir = base_dir / "data" / "cookies"
        cookie_file = cookie_dir / "bilibili_cookies.txt"

        if cookie_file.exists():
            logger.debug(f"Found Bilibili cookie file: {cookie_file}")
            return cookie_file

        return None

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取B站视频信息"""
        try:
            # 检查缓存
            cached_info = self._get_cached_info(url)
            if cached_info:
                logger.debug(f"Using cached info for: {url}")
                return cached_info

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                # B站增强反爬配置
                'http_headers': {
                    'Referer': 'https://www.bilibili.com/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"',
                },
                'socket_timeout': 30,
                'extractor_retries': 3,
                'fragment_retries': 3,
            }

            # 添加 Cookie 支持（用于访问大会员内容、登录专享等）
            cookie_path = self._get_bilibili_cookie_path()

            loop = asyncio.get_event_loop()

            def _extract_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            with cookiefile_for_ytdlp(cookie_path) as ytdlp_cookie_path:
                if ytdlp_cookie_path:
                    ydl_opts['cookiefile'] = str(ytdlp_cookie_path)
                    logger.info(f"Using Bilibili cookies from: {cookie_path}")

                info = await loop.run_in_executor(None, _extract_info)
            
            # 提取B站特有信息
            video_info = {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'description': info.get('description', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'uploader_id': info.get('uploader_id', ''),
                'upload_date': info.get('upload_date', ''),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'coin_count': info.get('coin_count', 0),  # B站特有：投币数
                'favorite_count': info.get('favorite_count', 0),  # B站特有：收藏数
                'danmaku_count': info.get('danmaku_count', 0),  # B站特有：弹幕数
                'platform': 'bilibili',
                'formats': self._extract_formats(info),
                'url': url,
                'tags': info.get('tags', []),
                'bvid': info.get('bvid', ''),  # B站特有：BV号
            }
            
            # 缓存结果
            self._cache_info(url, video_info)
            
            logger.info(f"Successfully extracted Bilibili info: {video_info['title']}")
            return video_info
            
        except Exception as e:
            logger.error(f"Error extracting Bilibili video info: {e}")
            raise Exception(f"Failed to get Bilibili video info: {str(e)}")
    
    async def download_video(
        self,
        url: str,
        quality: str = "best",
        output_path: Optional[str] = None,
        format_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """下载B站视频"""
        try:
            output_path = output_path or str(self.output_dir)
            
            # B站优化的下载选项
            ydl_opts = {
                'format': self._get_bilibili_format(quality, format_id),
                'outtmpl': f'{output_path}/%(title)s_{quality}.%(ext)s',
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [],
                'merge_output_format': 'mp4',
                # B站特殊HTTP头
                'http_headers': {
                    'Referer': 'https://www.bilibili.com/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                # 网络优化
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'skip_unavailable_fragments': True,
                'concurrent_fragment_downloads': 3,
                # B站需要处理分P视频
                'noplaylist': False,  # 如果是多P视频，下载所有分P
            }

            tool_mgr = get_tool_manager()
            ffmpeg_path = tool_mgr.get_ffmpeg_path()
            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = str(Path(ffmpeg_path).parent)

            # 添加 Cookie 支持（用于下载大会员内容、登录专享等）
            cookie_path = self._get_bilibili_cookie_path()
            
            # 添加进度钩子
            if progress_callback:
                # 获取当前事件循环供 progress_hook 使用
                loop = asyncio.get_event_loop()
                
                def progress_hook(d):
                    if d['status'] == 'downloading':
                        try:
                            downloaded = d.get('downloaded_bytes', 0)
                            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                            
                            if total > 0:
                                progress = (downloaded / total) * 100
                                speed = d.get('speed', 0)
                                eta = d.get('eta', 0)
                                
                                # 使用 run_coroutine_threadsafe 从非事件循环线程调度协程
                                asyncio.run_coroutine_threadsafe(
                                    progress_callback({
                                        'task_id': task_id,
                                        'status': 'downloading',
                                        'progress': round(progress, 2),
                                        'downloaded': downloaded,
                                        'total': total,
                                        'speed': speed,
                                        'eta': eta
                                    }),
                                    loop
                                )
                        except Exception as e:
                            logger.error(f"Progress callback error: {e}")
                    
                    elif d['status'] == 'finished':
                        asyncio.run_coroutine_threadsafe(
                            progress_callback({
                                'task_id': task_id,
                                'status': 'finished',
                                'filename': d.get('filename', '')
                            }),
                            loop
                        )
                
                ydl_opts['progress_hooks'].append(progress_hook)
            
            # 执行下载
            loop = asyncio.get_event_loop()
            
            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return {
                        'title': info.get('title', 'Unknown'),
                        'filename': ydl.prepare_filename(info),
                        'duration': info.get('duration', 0),
                        'filesize': info.get('filesize', 0),
                    }
            
            with cookiefile_for_ytdlp(cookie_path) as ytdlp_cookie_path:
                if ytdlp_cookie_path:
                    ydl_opts['cookiefile'] = str(ytdlp_cookie_path)
                    logger.info(f"Using Bilibili cookies for download from: {cookie_path}")

                result = await loop.run_in_executor(None, _download)
            
            logger.info(f"Successfully downloaded Bilibili video: {result['title']}")
            
            return {
                'status': 'success',
                'title': result['title'],
                'filename': result['filename'],
                'duration': result['duration'],
                'filesize': result['filesize'],
                'platform': 'bilibili',
                'download_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error downloading Bilibili video: {e}")
            if progress_callback and task_id:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(e)
                })
            raise Exception(f"Failed to download Bilibili video: {str(e)}")
    
    def _get_bilibili_format(self, quality: str, format_id: Optional[str] = None) -> str:
        """获取B站专用的格式选择器"""
        if format_id:
            fid = str(format_id).strip().lower()
            if fid not in ('mp4', 'mkv', 'webm', 'mp3'):
                return format_id
        
        # B站画质对应关系
        # 120: 4K超清, 116: 1080P60, 80: 1080P, 64: 720P, 32: 480P, 16: 360P
        bilibili_quality_map = {
            'best': 'bestvideo+bestaudio/best',
            '2160p': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',  # 4K
            '4k': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',     # 4K 别名
            '1440p': 'bestvideo[height<=1440]+bestaudio/best[height<=1440]',  # 2K
            '1080p60': 'bestvideo[height<=1080][fps<=60]+bestaudio/best[height<=1080]',
            '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
            '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
            'audio': 'bestaudio',
        }

        return bilibili_quality_map.get(quality.lower(), bilibili_quality_map['best'])
