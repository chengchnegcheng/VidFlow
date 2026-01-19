"""
Vimeo 专用下载器
针对 Vimeo 平台优化，支持私有视频和嵌入视频
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
from .proxy_config import get_ydl_proxy_opts

logger = logging.getLogger(__name__)


class VimeoDownloader(BaseDownloader):
    """Vimeo 专用下载器"""

    def __init__(self, output_dir: str = None):
        super().__init__(output_dir)
        self.platform_name = "vimeo"
    
    @staticmethod
    def supports_url(url: str) -> bool:
        """检查是否支持该URL"""
        url_lower = url.lower()
        return 'vimeo.com' in url_lower or 'player.vimeo.com' in url_lower
    
    def _get_vimeo_ydl_opts(self) -> dict:
        """获取 Vimeo 优化的 yt-dlp 配置"""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            # Vimeo 特定的 HTTP 头
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Referer': 'https://vimeo.com/',
            },
            # 超时配置
            'socket_timeout': 60,
            # 重试配置
            'retries': 10,
            'fragment_retries': 10,
            # 代理配置
            **get_ydl_proxy_opts(),
        }
    
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取 Vimeo 视频信息"""
        try:
            logger.info(f"[VimeoDownloader] get_video_info called for: {url}")

            # 检查缓存
            cached_info = self._get_cached_info(url)
            if cached_info:
                logger.debug(f"Using cached info for: {url}")
                return cached_info
            
            ydl_opts = self._get_vimeo_ydl_opts()
            
            # 获取 Cookie
            cookie_path = self._get_vimeo_cookie_path()
            
            loop = asyncio.get_event_loop()
            
            def _extract_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            with cookiefile_for_ytdlp(cookie_path) as ytdlp_cookie_path:
                if ytdlp_cookie_path:
                    ydl_opts['cookiefile'] = str(ytdlp_cookie_path)
                    logger.info(f"Using Vimeo cookies from: {cookie_path}")
                
                info = await loop.run_in_executor(None, _extract_info)
            
            # 提取视频信息
            video_info = {
                'title': info.get('title', 'Vimeo Video'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'description': info.get('description', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'upload_date': info.get('upload_date', ''),
                'view_count': info.get('view_count', 0),
                'platform': 'vimeo',
                'formats': self._extract_formats(info),
                'url': url
            }
            
            # 缓存结果
            self._cache_info(url, video_info)
            
            logger.info(f"[VimeoDownloader] Successfully extracted info: {video_info['title']}")
            return video_info
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Error extracting Vimeo video info: {e}")
            
            # 友好的错误提示
            if "private" in error_str.lower() or "password" in error_str.lower():
                raise Exception("该视频是私有视频，需要登录或密码才能访问。请在设置中配置 Vimeo Cookie。")
            elif "not found" in error_str.lower() or "404" in error_str:
                raise Exception("视频不存在或已被删除")
            elif "geo" in error_str.lower() or "country" in error_str.lower():
                raise Exception("该视频在您所在地区不可用，请尝试使用代理")
            elif "timeout" in error_str.lower():
                raise Exception("获取视频信息超时，请检查网络连接")
            else:
                raise Exception(f"获取 Vimeo 视频信息失败: {error_str}")
    
    async def download_video(
        self,
        url: str,
        quality: str = "best",
        output_path: Optional[str] = None,
        format_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """下载 Vimeo 视频"""
        try:
            output_path = output_path or str(self.output_dir)
            
            # 处理输出格式
            output_format: Optional[str] = None
            if format_id:
                fid = str(format_id).strip().lower()
                if fid in ('mp4', 'mkv', 'webm', 'mp3'):
                    output_format = fid
            
            format_quality = 'audio' if output_format == 'mp3' else quality
            merge_format = output_format if output_format in ('mp4', 'mkv', 'webm') else 'mp4'
            
            ydl_opts = self._get_vimeo_ydl_opts()
            ydl_opts.update({
                'format': self._get_format_selector(format_quality, format_id),
                'outtmpl': f'{output_path}/%(title)s_{quality}.%(ext)s',
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [],
                'merge_output_format': merge_format,
                # 网络优化
                'concurrent_fragment_downloads': 4,
                'http_chunk_size': 10485760,
            })
            
            # 设置 ffmpeg 路径
            tool_mgr = get_tool_manager()
            ffmpeg_path = tool_mgr.get_ffmpeg_path()
            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = str(Path(ffmpeg_path).parent)
            
            # 音频提取
            if output_format == 'mp3':
                ydl_opts.pop('merge_output_format', None)
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '0',
                }]
            
            # 获取 Cookie
            cookie_path = self._get_vimeo_cookie_path()
            
            # 取消检查
            cancel_checker = None
            if task_id:
                try:
                    from src.core.download_queue import get_download_queue
                    cancel_checker = get_download_queue()
                except Exception:
                    pass
            
            # 进度回调
            if progress_callback:
                loop = asyncio.get_event_loop()
                
                # 用于跟踪多分片下载的累积进度
                progress_state = {
                    'total_downloaded': 0,
                    'estimated_total': 0,
                    'last_progress': 0,
                    'fragment_index': 0,
                    'fragment_count': 0,
                }
                
                def progress_hook(d):
                    if cancel_checker and task_id and cancel_checker.is_task_cancelled_sync(task_id):
                        raise Exception("Download cancelled by user")
                    
                    if d['status'] == 'downloading':
                        try:
                            downloaded = d.get('downloaded_bytes', 0)
                            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                            speed = d.get('speed', 0)
                            eta = d.get('eta', 0)
                            
                            # 获取分片信息
                            fragment_index = d.get('fragment_index', 0)
                            fragment_count = d.get('fragment_count', 0)
                            
                            # 计算进度
                            if fragment_count > 0:
                                fragment_progress = (downloaded / total) if total > 0 else 0
                                progress = ((fragment_index + fragment_progress) / fragment_count) * 100
                                progress_state['fragment_index'] = fragment_index
                                progress_state['fragment_count'] = fragment_count
                                if fragment_index > 0:
                                    avg_fragment_size = (progress_state['total_downloaded'] + downloaded) / (fragment_index + fragment_progress)
                                    progress_state['estimated_total'] = int(avg_fragment_size * fragment_count)
                                if fragment_progress >= 0.99:
                                    progress_state['total_downloaded'] += total
                            elif total > 0:
                                progress = (downloaded / total) * 100
                                progress_state['estimated_total'] = total
                            else:
                                progress = progress_state['last_progress']
                            
                            progress = max(progress, progress_state['last_progress'])
                            progress_state['last_progress'] = progress
                            
                            display_total = progress_state['estimated_total'] if progress_state['estimated_total'] > 0 else total
                            display_downloaded = int(display_total * progress / 100) if display_total > 0 else downloaded
                            
                            asyncio.run_coroutine_threadsafe(
                                progress_callback({
                                    'task_id': task_id,
                                    'status': 'downloading',
                                    'progress': round(progress, 1),
                                    'downloaded': display_downloaded,
                                    'total': display_total,
                                    'speed': speed,
                                    'eta': eta
                                }),
                                loop
                            )
                        except Exception as e:
                            if "cancelled" in str(e).lower():
                                raise
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
                    logger.info(f"Using Vimeo cookies for download")
                
                result = await loop.run_in_executor(None, _download)
            
            logger.info(f"[VimeoDownloader] Successfully downloaded: {result['title']}")
            
            return {
                'status': 'success',
                'title': result['title'],
                'filename': result['filename'],
                'duration': result['duration'],
                'filesize': result['filesize'],
                'platform': 'vimeo',
                'download_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Error downloading Vimeo video: {e}")
            
            if progress_callback and task_id:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(e)
                })
            
            # 友好的错误提示
            if "private" in error_str.lower() or "password" in error_str.lower():
                raise Exception("该视频是私有视频，需要登录或密码才能访问")
            elif "cancelled" in error_str.lower():
                raise Exception("下载已取消")
            else:
                raise Exception(f"下载失败: {error_str}")
    
    def _get_vimeo_cookie_path(self) -> Optional[Path]:
        """获取 Vimeo Cookie 文件路径"""
        from .cookie_manager import get_cookie_base_dir
        cookie_dir = get_cookie_base_dir()
        cookie_file = cookie_dir / "vimeo_cookies.txt"

        if cookie_file.exists():
            logger.info(f"[VimeoDownloader] Found vimeo cookie: {cookie_file}")
            return cookie_file

        return None
