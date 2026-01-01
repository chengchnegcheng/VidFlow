"""
YouTube 专用下载器
针对 YouTube 进行优化
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import yt_dlp
from src.core.tool_manager import get_tool_manager
from src.core.cookie_storage import cookiefile_for_ytdlp
from .base_downloader import BaseDownloader
from .proxy_config import get_ydl_proxy_opts

logger = logging.getLogger(__name__)


class YoutubeDownloader(BaseDownloader):
    """YouTube 专用下载器"""
    
    def __init__(self, output_dir: str = "./data/downloads"):
        super().__init__(output_dir)
        self.platform_name = "youtube"
    
    @staticmethod
    def supports_url(url: str) -> bool:
        """检查是否支持该URL"""
        url_lower = url.lower()
        return 'youtube.com' in url_lower or 'youtu.be' in url_lower
    
    def _get_youtube_cookie_path(self) -> Optional[Path]:
        """
        获取 YouTube Cookie 文件路径
        
        Returns:
            Cookie 文件路径，如果不存在则返回 None
        """
        # Cookie 文件存储位置
        base_dir = Path(__file__).parent.parent.parent.parent
        cookie_dir = base_dir / "data" / "cookies"
        cookie_file = cookie_dir / "youtube_cookies.txt"
        
        if cookie_file.exists():
            logger.debug(f"Found YouTube cookie file: {cookie_file}")
            return cookie_file
        
        return None
    
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取YouTube视频信息"""
        try:
            # 检查缓存
            cached_info = self._get_cached_info(url)
            if cached_info:
                logger.debug(f"Using cached info for: {url}")
                return cached_info
            
            # 获取代理配置
            proxy_opts = get_ydl_proxy_opts()
            if proxy_opts.get('proxy'):
                logger.info(f"[YouTube] Using proxy: {proxy_opts['proxy']}")
            else:
                logger.info("[YouTube] No proxy configured")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                },
                'socket_timeout': 30,
                # 代理配置
                **proxy_opts,
            }
            
            # 添加 Cookie 支持（仅在用户已配置时使用）
            cookie_path = self._get_youtube_cookie_path()
            # 不再自动从浏览器获取 Cookie，避免不必要的错误
            # 如果需要 Cookie，会在下载失败时提示用户配置

            loop = asyncio.get_event_loop()

            with cookiefile_for_ytdlp(cookie_path) as ytdlp_cookie_path:
                if ytdlp_cookie_path:
                    ydl_opts['cookiefile'] = str(ytdlp_cookie_path)
                    logger.info(f"Using YouTube cookies from: {cookie_path}")

                player_client_attempts = [
                    ['android_sdkless', 'web_safari'],  # 新版 yt-dlp 默认配置
                    ['android_sdkless'],
                    ['web_safari'],
                    None,
                    ['ios'],
                    ['android'],
                ]

                info = None
                last_error: Optional[Exception] = None
                for player_clients in player_client_attempts:
                    attempt_opts = ydl_opts.copy()
                    attempt_opts['http_headers'] = ydl_opts.get('http_headers', {}).copy()
                    if player_clients:
                        attempt_opts['extractor_args'] = {
                            'youtube': {
                                'player_client': player_clients,
                            }
                        }

                    def _extract_info():
                        with yt_dlp.YoutubeDL(attempt_opts) as ydl:
                            return ydl.extract_info(url, download=False)

                    try:
                        info = await loop.run_in_executor(None, _extract_info)
                        break
                    except Exception as e:
                        last_error = e
                        err_lower = str(e).lower()
                        # 可重试的错误关键词（这些错误可能通过切换 player_client 解决）
                        retryable_keywords = [
                            'failed to extract any player response',
                            'please sign in',
                            'sign in',
                            "confirm you're not a bot",
                            'confirm your age',
                            'http error 403',
                            'forbidden',
                        ]
                        if any(keyword in err_lower for keyword in retryable_keywords):
                            logger.warning(f"YouTube info extraction failed (player_client={player_clients}), retrying with different client...")
                            continue
                        raise

            if info is None and last_error is not None:
                raise last_error
            
            # 提取YouTube特有信息
            video_info = {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'description': info.get('description', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'uploader_id': info.get('uploader_id', ''),
                'channel': info.get('channel', ''),
                'channel_id': info.get('channel_id', ''),
                'upload_date': info.get('upload_date', ''),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'comment_count': info.get('comment_count', 0),
                'platform': 'youtube',
                'formats': self._extract_formats(info),
                'url': url,
                'categories': info.get('categories', []),
                'tags': info.get('tags', []),
            }
            
            # 缓存结果
            self._cache_info(url, video_info)
            
            logger.info(f"Successfully extracted YouTube info: {video_info['title']}")
            return video_info
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error extracting YouTube video info: {error_msg}")

            # 检测是否真正需要 Cookie（登录验证）
            needs_cookie_keywords = [
                'sign in',
                'login required',
                'members-only',
                'private video',
                'this video is private',
                'confirm you\'re not a bot',
                'confirm your age'
            ]

            if any(keyword in error_msg.lower() for keyword in needs_cookie_keywords):
                # 真正需要 Cookie 的情况
                friendly_error = (
                    "该视频需要登录才能访问。\n\n"
                    "💡 解决方法：\n"
                    "1. 在「系统设置 → Cookie 管理」中配置 YouTube Cookie\n"
                    "2. 使用浏览器扩展（如 Cookie Editor）导出 Cookie\n"
                    "3. 或使用自动获取 Cookie 功能（需要关闭 Chrome）"
                )
            elif 'failed to extract any player response' in error_msg.lower():
                friendly_error = (
                    "YouTube 解析失败：无法提取播放器响应。\n\n"
                    "💡 可能原因：\n"
                    "1. YouTube 近期更新了页面/接口\n"
                    "2. 网络/代理不稳定导致播放器接口请求异常\n"
                    "3. 需要配置 Cookie（部分地区/账号/视频会触发验证）\n\n"
                    "✅ 建议操作：\n"
                    "1. 确认代理可用后重试\n"
                    "2. 在「系统设置 → Cookie 管理」中配置 YouTube Cookie\n"
                    "3. 如仍失败，请在终端执行 `yt-dlp -U` 或更新后端依赖的 yt-dlp 版本\n\n"
                    f"详细错误: {error_msg}"
                )
            else:
                # 其他错误，直接返回原始错误信息
                friendly_error = error_msg

            raise Exception(f"获取视频信息失败: {friendly_error}")
    
    async def download_video(
        self,
        url: str,
        quality: str = "best",
        output_path: Optional[str] = None,
        format_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """下载YouTube视频"""
        try:
            output_path = output_path or str(self.output_dir)
            output_format: Optional[str] = None
            if format_id:
                fid = str(format_id).strip().lower()
                if fid in ('mp4', 'mkv', 'webm', 'mp3'):
                    output_format = fid

            format_quality = 'audio' if output_format == 'mp3' else quality
            merge_format = output_format if output_format in ('mp4', 'mkv', 'webm') else 'mp4'
            
            # YouTube 优化的下载选项
            ydl_opts = {
                'format': self._get_format_selector(format_quality, format_id),
                'outtmpl': f'{output_path}/%(title)s_{quality}.%(ext)s',
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [],
                'merge_output_format': merge_format,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'Origin': 'https://www.youtube.com',
                    'Referer': 'https://www.youtube.com/',
                },
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'skip_unavailable_fragments': True,
                'concurrent_fragment_downloads': 4,
                'http_chunk_size': 10485760,
                # 代理配置
                **get_ydl_proxy_opts(),
            }

            po_token = os.environ.get('YTDLP_YOUTUBE_PO_TOKEN')
            if po_token:
                ydl_opts['extractor_args']['youtube']['po_token'] = po_token

            tool_mgr = get_tool_manager()
            ffmpeg_path = tool_mgr.get_ffmpeg_path()
            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = str(Path(ffmpeg_path).parent)

            if output_format == 'mp3':
                ydl_opts.pop('merge_output_format', None)
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '0',
                }]
            
            # 添加 Cookie 支持（仅在用户已配置时使用）
            cookie_path = self._get_youtube_cookie_path()
            # 不再自动从浏览器获取 Cookie，避免不必要的错误
            
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
            player_client_attempts = [
                ['android_sdkless', 'web_safari'],  # 新版 yt-dlp 默认配置
                ['android_sdkless'],
                ['web_safari'],
                None,
                ['ios'],
                ['android'],
            ]

            result = None
            last_error: Optional[Exception] = None

            with cookiefile_for_ytdlp(cookie_path) as ytdlp_cookie_path:
                if ytdlp_cookie_path:
                    ydl_opts['cookiefile'] = str(ytdlp_cookie_path)
                    logger.info(f"Using YouTube cookies for download from: {cookie_path}")

                for player_clients in player_client_attempts:
                    attempt_opts = ydl_opts.copy()
                    attempt_opts['http_headers'] = ydl_opts.get('http_headers', {}).copy()

                    youtube_args = {}
                    if player_clients:
                        youtube_args['player_client'] = player_clients
                    if po_token:
                        youtube_args['po_token'] = po_token

                    if youtube_args:
                        attempt_opts['extractor_args'] = {'youtube': youtube_args}

                    def _download_with_opts():
                        with yt_dlp.YoutubeDL(attempt_opts) as ydl:
                            info = ydl.extract_info(url, download=True)
                            return {
                                'title': info.get('title', 'Unknown'),
                                'filename': ydl.prepare_filename(info),
                                'duration': info.get('duration', 0),
                                'filesize': info.get('filesize', 0),
                            }

                    try:
                        result = await loop.run_in_executor(None, _download_with_opts)
                        break
                    except Exception as e:
                        last_error = e
                        err_lower = str(e).lower()
                        retryable_keywords = [
                            'please sign in',
                            'sign in',
                            'login required',
                            'members-only',
                            'private video',
                            "confirm you're not a bot",
                            'confirm your age',
                            'failed to extract any player response',
                            'http error 403',
                            'forbidden',
                        ]
                        if any(keyword in err_lower for keyword in retryable_keywords):
                            logger.warning(f"YouTube download failed (player_client={player_clients}), retrying fallback...")
                            continue
                        raise

            if result is None and last_error is not None:
                raise last_error
            
            logger.info(f"Successfully downloaded YouTube video: {result['title']}")
            
            return {
                'status': 'success',
                'title': result['title'],
                'filename': result['filename'],
                'duration': result['duration'],
                'filesize': result['filesize'],
                'platform': 'youtube',
                'download_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error downloading YouTube video: {error_msg}")

            needs_cookie_keywords = [
                'please sign in',
                'sign in',
                'login required',
                'members-only',
                'private video',
                'this video is private',
                "confirm you're not a bot",
                'confirm your age'
            ]

            # 检测 Chrome Cookie 数据库访问错误
            if 'could not copy chrome cookie' in error_msg.lower() or 'cookie database' in error_msg.lower():
                friendly_error = (
                    "无法访问 Chrome Cookie 数据库。\n\n"
                    "💡 解决方法：\n"
                    "1. 关闭所有 Chrome 浏览器窗口后重试\n"
                    "2. 或在「系统设置 → Cookie 管理」中手动配置 YouTube Cookie\n"
                    "3. 使用浏览器扩展（如 Cookie Editor）导出 Cookie 文件\n\n"
                    f"详细错误: {error_msg}"
                )
            elif any(keyword in error_msg.lower() for keyword in needs_cookie_keywords):
                friendly_error = (
                    "该 YouTube 视频需要登录/验证才能下载。\n\n"
                    "💡 解决方法：\n"
                    "1. 在「系统设置 → Cookie 管理」中配置 YouTube Cookie\n"
                    "2. 重新获取 Cookie 后重试\n\n"
                    f"详细错误: {error_msg}"
                )
            else:
                friendly_error = error_msg

            if progress_callback and task_id:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'error',
                    'error': friendly_error
                })
            raise Exception(f"下载失败: {friendly_error}")
