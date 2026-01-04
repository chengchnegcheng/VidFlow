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
from .proxy_config import get_ydl_proxy_opts

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
        # 使用统一的 Cookie 目录获取函数（支持打包环境）
        from .cookie_manager import get_cookie_base_dir
        from src.core.cookie_storage import read_cookie_file, is_encrypted_cookie_file_text
        
        cookie_dir = get_cookie_base_dir()
        cookie_file = cookie_dir / "bilibili_cookies.txt"

        logger.info(f"[Bilibili] Looking for cookie file at: {cookie_file}")
        
        if cookie_file.exists():
            # 检查文件大小和内容
            file_size = cookie_file.stat().st_size
            logger.info(f"[Bilibili] Found cookie file, size: {file_size} bytes")
            
            # 检查是否包含关键 Cookie（需要先解密）
            try:
                raw_content = cookie_file.read_text(encoding='utf-8', errors='ignore')
                
                # 如果是加密的，尝试解密后检查
                if is_encrypted_cookie_file_text(raw_content):
                    logger.info("[Bilibili] Cookie file is encrypted, will be decrypted when used")
                    # 加密文件无法直接检查内容，返回路径让后续解密处理
                    return cookie_file
                
                # 未加密的文件，直接检查内容
                has_sessdata = 'SESSDATA' in raw_content
                has_bili_jct = 'bili_jct' in raw_content
                has_dedeuserid = 'DedeUserID' in raw_content
                logger.info(f"[Bilibili] Cookie check - SESSDATA: {has_sessdata}, bili_jct: {has_bili_jct}, DedeUserID: {has_dedeuserid}")
                
                if not (has_sessdata and has_bili_jct and has_dedeuserid):
                    logger.warning("[Bilibili] Cookie file may be incomplete! Missing required fields for HD video access.")
            except Exception as e:
                logger.warning(f"[Bilibili] Failed to check cookie content: {e}")
            
            return cookie_file
        
        logger.info("[Bilibili] Cookie file not found")
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
                # B站特殊选项
                'http_headers': {
                    'Referer': 'https://www.bilibili.com/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                # 代理配置（B站国内不需要，但保持一致性）
                **get_ydl_proxy_opts(),
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
            
        except RuntimeError as e:
            # Cookie 解密失败的特殊处理
            error_msg = str(e)
            if '无法解密' in error_msg or 'decrypt' in error_msg.lower():
                logger.error(f"[Bilibili] Cookie decryption failed: {e}")
                raise Exception(
                    "B站 Cookie 解密失败。\n\n"
                    "💡 可能原因：Cookie 是在其他 Windows 用户账户下保存的。\n\n"
                    "解决方法：\n"
                    "1. 打开「Cookie 管理」\n"
                    "2. 删除现有的 B站 Cookie\n"
                    "3. 重新获取 Cookie（使用当前 Windows 账户）\n\n"
                    "注意：即使没有 Cookie，也可以下载非会员视频。"
                )
            raise Exception(f"Failed to get Bilibili video info: {error_msg}")
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
                # 代理配置（B站国内不需要，但保持一致性）
                **get_ydl_proxy_opts(),
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
                    logger.info(f"[Bilibili] Using cookies for download from: {cookie_path}")
                    logger.info(f"[Bilibili] yt-dlp cookie file: {ytdlp_cookie_path}")
                else:
                    logger.warning("[Bilibili] No cookie file available - HD video may not be accessible!")

                # 记录使用的格式选择器
                logger.info(f"[Bilibili] Format selector: {ydl_opts.get('format')}")
                
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
            
        except RuntimeError as e:
            # Cookie 解密失败的特殊处理
            error_msg = str(e)
            if '无法解密' in error_msg or 'decrypt' in error_msg.lower():
                logger.error(f"[Bilibili] Cookie decryption failed: {e}")
                raise Exception(
                    "B站 Cookie 解密失败。\n\n"
                    "💡 可能原因：Cookie 是在其他 Windows 用户账户下保存的。\n\n"
                    "解决方法：\n"
                    "1. 打开「Cookie 管理」\n"
                    "2. 删除现有的 B站 Cookie\n"
                    "3. 重新获取 Cookie（使用当前 Windows 账户）\n\n"
                    "注意：即使没有 Cookie，也可以下载非会员视频。"
                )
            raise Exception(f"Failed to download Bilibili video: {error_msg}")
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
        """获取B站专用的格式选择器
        
        优先选择 H.264 (avc1) 编码，确保在手机和微信等应用中兼容播放
        """
        if format_id:
            fid = str(format_id).strip().lower()
            if fid not in ('mp4', 'mkv', 'webm', 'mp3'):
                return format_id
        
        # B站画质对应关系
        # 120: 4K超清, 116: 1080P60, 80: 1080P, 64: 720P, 32: 480P, 16: 360P
        # 优先 H.264 编码确保手机兼容性
        bilibili_quality_map = {
            'best': 'bestvideo[vcodec^=avc]+bestaudio/bestvideo+bestaudio/best',
            '2160p': 'bestvideo[height<=2160][vcodec^=avc]+bestaudio/bestvideo[height<=2160]+bestaudio/best[height<=2160]',  # 4K
            '4k': 'bestvideo[height<=2160][vcodec^=avc]+bestaudio/bestvideo[height<=2160]+bestaudio/best[height<=2160]',     # 4K 别名
            '1440p': 'bestvideo[height<=1440][vcodec^=avc]+bestaudio/bestvideo[height<=1440]+bestaudio/best[height<=1440]',  # 2K
            '1080p60': 'bestvideo[height<=1080][fps<=60][vcodec^=avc]+bestaudio/bestvideo[height<=1080][fps<=60]+bestaudio/best[height<=1080]',
            '1080p': 'bestvideo[height<=1080][vcodec^=avc]+bestaudio/bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            '720p': 'bestvideo[height<=720][vcodec^=avc]+bestaudio/bestvideo[height<=720]+bestaudio/best[height<=720]',
            '480p': 'bestvideo[height<=480][vcodec^=avc]+bestaudio/bestvideo[height<=480]+bestaudio/best[height<=480]',
            '360p': 'bestvideo[height<=360][vcodec^=avc]+bestaudio/bestvideo[height<=360]+bestaudio/best[height<=360]',
            'audio': 'bestaudio',
        }

        return bilibili_quality_map.get(quality.lower(), bilibili_quality_map['best'])
