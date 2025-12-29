"""
通用下载器
作为后备方案，支持所有 yt-dlp 支持的平台
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


class GenericDownloader(BaseDownloader):
    """通用下载器，支持所有yt-dlp支持的平台"""
    
    def __init__(self, output_dir: str = "./data/downloads"):
        super().__init__(output_dir)
        self.platform_name = "generic"
        # 智能回退模式下是否使用 Cookie（由 DownloaderFactory 设置）
        self._use_cookie_in_smart_mode = True
    
    @staticmethod
    def supports_url(url: str) -> bool:
        """通用下载器支持所有URL"""
        return True
    
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息"""
        try:
            # 检查缓存
            cached_info = self._get_cached_info(url)
            if cached_info:
                logger.debug(f"Using cached info for: {url}")
                return cached_info

            # 检测平台以优化配置
            platform = self._detect_platform(url)

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                # 通用反爬配置
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en-US,en;q=0.8',
                    # 注意：不要设置 Accept-Encoding，让 yt-dlp 自动处理压缩
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                },
                # 超时配置
                'socket_timeout': 30,
            }

            # 针对国内平台优化
            if platform in ['xiaohongshu', 'douyin', 'weixin', 'tencent', 'youku', 'iqiyi', 'bilibili']:
                ydl_opts['geo_bypass'] = True
                ydl_opts['geo_bypass_country'] = 'CN'
                # 添加 Referer 避免403
                if platform == 'xiaohongshu':
                    ydl_opts['http_headers']['Referer'] = 'https://www.xiaohongshu.com/'
                elif platform == 'bilibili':
                    ydl_opts['http_headers']['Referer'] = 'https://www.bilibili.com/'
                elif platform in ['tencent', 'youku', 'iqiyi']:
                    # 国内视频平台通用 Referer
                    ydl_opts['http_headers']['Referer'] = url.split('?')[0]  # 使用当前页面作为 Referer

            # 为特定平台添加 Cookie 支持（仅在非智能回退模式或允许使用 Cookie 时）
            cookie_path = None
            if getattr(self, '_use_cookie_in_smart_mode', True):
                cookie_path = self._get_platform_cookie_path(url)

            loop = asyncio.get_event_loop()

            def _extract_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            with cookiefile_for_ytdlp(cookie_path) as ytdlp_cookie_path:
                if ytdlp_cookie_path:
                    ydl_opts['cookiefile'] = str(ytdlp_cookie_path)
                    logger.info(f"Using cookies from: {cookie_path}")

                info = await loop.run_in_executor(None, _extract_info)
            
            # 提取通用信息
            video_info = {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'description': info.get('description', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'upload_date': info.get('upload_date', ''),
                'view_count': info.get('view_count', 0),
                'platform': self._detect_platform(url),
                'formats': self._extract_formats(info),
                'url': url
            }
            
            # 缓存结果
            self._cache_info(url, video_info)
            
            logger.info(f"Successfully extracted info: {video_info['title']}")
            return video_info
            
        except Exception as e:
            logger.error(f"Error extracting video info: {e}")
            raise Exception(f"Failed to get video info: {str(e)}")
    
    async def download_video(
        self,
        url: str,
        quality: str = "best",
        output_path: Optional[str] = None,
        format_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """下载视频"""
        try:
            output_path = output_path or str(self.output_dir)

            output_format: Optional[str] = None
            if format_id:
                fid = str(format_id).strip().lower()
                if fid in ('mp4', 'mkv', 'webm', 'mp3'):
                    output_format = fid

            format_quality = 'audio' if output_format == 'mp3' else quality
            merge_format = output_format if output_format in ('mp4', 'mkv', 'webm') else 'mp4'

            # 检测平台以优化配置
            platform = self._detect_platform(url)

            # 通用下载选项
            ydl_opts = {
                'format': self._get_format_selector(format_quality, format_id),
                'outtmpl': f'{output_path}/%(title)s_{quality}.%(ext)s',
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [],
                'merge_output_format': merge_format,
                # 通用反爬配置
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en-US,en;q=0.8',
                    # 注意：不要设置 Accept-Encoding，让 yt-dlp 自动处理压缩
                    'DNT': '1',
                    'Connection': 'keep-alive',
                },
                # 网络优化
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'skip_unavailable_fragments': True,
                'concurrent_fragment_downloads': 3,
                'http_chunk_size': 10485760,
            }

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

            # 针对国内平台优化
            if platform in ['xiaohongshu', 'douyin', 'weixin', 'tencent', 'youku', 'iqiyi', 'bilibili']:
                ydl_opts['geo_bypass'] = True
                ydl_opts['geo_bypass_country'] = 'CN'
                # 添加 Referer 避免403
                if platform == 'xiaohongshu':
                    ydl_opts['http_headers']['Referer'] = 'https://www.xiaohongshu.com/'
                elif platform == 'bilibili':
                    ydl_opts['http_headers']['Referer'] = 'https://www.bilibili.com/'
                elif platform in ['tencent', 'youku', 'iqiyi']:
                    ydl_opts['http_headers']['Referer'] = url.split('?')[0]

            # 为特定平台添加 Cookie 支持（仅在非智能回退模式或允许使用 Cookie 时）
            cookie_path = None
            if getattr(self, '_use_cookie_in_smart_mode', True):
                cookie_path = self._get_platform_cookie_path(url)
            
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
                    logger.info(f"Using cookies for download from: {cookie_path}")

                result = await loop.run_in_executor(None, _download)
            
            logger.info(f"Successfully downloaded: {result['title']}")
            
            return {
                'status': 'success',
                'title': result['title'],
                'filename': result['filename'],
                'duration': result['duration'],
                'filesize': result['filesize'],
                'platform': self._detect_platform(url),
                'download_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            if progress_callback and task_id:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(e)
                })
            raise Exception(f"Failed to download video: {str(e)}")
    
    def _detect_platform(self, url: str) -> str:
        """检测视频平台"""
        url_lower = url.lower()

        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'bilibili.com' in url_lower:
            return 'bilibili'
        # ✅ 先检查 TikTok，再检查 Douyin（避免误匹配）
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'douyin.com' in url_lower or 'v.douyin.com' in url_lower:
            return 'douyin'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'twitter'
        elif 'instagram.com' in url_lower:
            return 'instagram'
        elif 'facebook.com' in url_lower:
            return 'facebook'
        elif 'xiaohongshu.com' in url_lower:
            return 'xiaohongshu'
        elif 'weixin' in url_lower or 'qq.com/channels' in url_lower:
            return 'weixin'
        elif 'v.qq.com' in url_lower:
            return 'tencent'
        elif 'youku.com' in url_lower:
            return 'youku'
        elif 'iqiyi.com' in url_lower:
            return 'iqiyi'
        else:
            return 'generic'
    
    def _get_platform_cookie_path(self, url: str) -> Optional[Path]:
        """
        根据 URL 获取对应平台的 Cookie 文件路径
        
        Args:
            url: 视频URL
            
        Returns:
            Cookie 文件路径，如果不存在则返回 None
        """
        base_dir = Path(__file__).parent.parent.parent.parent
        cookie_dir = base_dir / "data" / "cookies"
        
        # 根据平台选择 Cookie 文件
        platform = self._detect_platform(url)
        
        # 平台与 Cookie 文件的映射
        cookie_map = {
            'xiaohongshu': 'xiaohongshu_cookies.txt',
            'douyin': 'douyin_cookies.txt',
            'tiktok': 'tiktok_cookies.txt',
            'bilibili': 'bilibili_cookies.txt',
            'youtube': 'youtube_cookies.txt',
            'twitter': 'twitter_cookies.txt',
            'instagram': 'instagram_cookies.txt',
        }
        
        cookie_filename = cookie_map.get(platform)
        if not cookie_filename:
            return None
        
        cookie_file = cookie_dir / cookie_filename
        if cookie_file.exists():
            logger.debug(f"Found cookie file for {platform}: {cookie_file}")
            return cookie_file
        
        return None
