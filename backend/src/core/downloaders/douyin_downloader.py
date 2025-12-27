"""
抖音/TikTok 专用下载器
针对抖音和TikTok平台优化，处理短链接和反爬虫机制
"""
import asyncio
import logging
import re
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import yt_dlp
from src.core.cookie_storage import cookiefile_for_ytdlp, write_cookie_file
from .base_downloader import BaseDownloader

logger = logging.getLogger(__name__)


class DouyinDownloader(BaseDownloader):
    """抖音/TikTok 专用下载器"""

    def __init__(self, output_dir: str = "./data/downloads"):
        super().__init__(output_dir)
        self.platform_name = "douyin"
        self._url_cache = {}  # 短链接缓存
    
    @staticmethod
    def supports_url(url: str) -> bool:
        """检查是否支持该URL"""
        url_lower = url.lower()
        return any([
            'douyin.com' in url_lower,
            'tiktok.com' in url_lower,
            'v.douyin.com' in url_lower,  # 短链接
        ])
    
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取抖音/TikTok视频信息"""
        try:
            logger.info(f"[NEW CODE 7.0] DouyinDownloader.get_video_info called for: {url}")

            # 检查缓存
            cached_info = self._get_cached_info(url)
            if cached_info:
                logger.debug(f"Using cached info for: {url}")
                return cached_info

            # 处理短链接重定向
            logger.info(f"[NEW CODE 7.0] Resolving short URL...")
            resolved_url = await self._resolve_short_url(url)
            logger.info(f"[NEW CODE 7.0] URL resolved, extracting video info...")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                # 抖音增强反爬配置
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Referer': 'https://www.douyin.com/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                },
                'socket_timeout': 30,
                'extractor_retries': 3,
                'fragment_retries': 3,
                'geo_bypass': True,
                'geo_bypass_country': 'CN',
                'verbose': True,
            }

            # 仅使用已配置的 Cookie 文件
            cookie_path = self._get_douyin_cookie_path()
            # 不再自动从浏览器提取 Cookie

            loop = asyncio.get_event_loop()

            def _extract_info():
                logger.info(f"[NEW CODE 7.0] Calling yt-dlp.extract_info for: {resolved_url}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(resolved_url, download=False)
                    logger.info(f"[NEW CODE 7.0] yt-dlp extraction completed successfully")
                    return result

            with cookiefile_for_ytdlp(cookie_path) as ytdlp_cookie_path:
                if ytdlp_cookie_path:
                    ydl_opts['cookiefile'] = str(ytdlp_cookie_path)
                    logger.info(f"Using Douyin cookies from: {cookie_path}")

                info = await loop.run_in_executor(None, _extract_info)
            
            # 提取抖音特有信息
            result = {
                'title': info.get('title', 'Unknown'),
                'url': resolved_url,
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'uploader': info.get('uploader') or info.get('creator'),
                'upload_date': info.get('upload_date'),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'description': info.get('description', ''),
                'formats': self._parse_formats(info.get('formats', [])),
                'platform': 'tiktok' if 'tiktok.com' in resolved_url else 'douyin',
                'raw_info': info
            }
            
            # 缓存结果
            self._cache_info(url, result)
            
            return result
        except Exception as e:
            logger.error(f"Error extracting Douyin/TikTok video info: {e}")
            raise Exception(f"Failed to get video info: {str(e)}")
    
    async def download_video(
        self,
        url: str,
        quality: str = "best",
        output_format: str = "mp4",
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        下载抖音/TikTok视频
        
        Args:
            url: 视频URL（支持短链接）
            quality: 画质选择
            output_format: 输出格式
            progress_callback: 进度回调函数
            **kwargs: 额外参数（如cookie等）
        """
        try:
            # 处理短链接
            resolved_url = await self._resolve_short_url(url)
            
            # 获取视频信息用于文件命名
            info = await self.get_video_info(resolved_url)
            
            # 构建安全的文件名
            safe_title = self._sanitize_filename(info['title'])
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"{safe_title}_{timestamp}.%(ext)s"
            output_path = self.output_dir / output_filename
            
            # 获取事件循环
            loop = asyncio.get_event_loop()
            
            # 配置下载选项
            ydl_opts = {
                'format': self._get_format_selector(quality, output_format),
                'outtmpl': str(output_path),
                'progress_hooks': [self._create_progress_hook(progress_callback, loop)] if progress_callback else [],
                'merge_output_format': output_format,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
                    'Referer': 'https://www.douyin.com/',
                },
                # 抖音特定配置
                'geo_bypass': True,
                'geo_bypass_country': 'CN',
                'nocheckcertificate': True,  # 跳过证书验证
                'socket_timeout': 30,
                'retries': 5,
                # 无水印下载（如果可能）
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': output_format,
                }],
            }
            
            # 添加 Cookie 支持（优先使用传入的，否则使用配置的）
            cookie_path: Optional[Path] = None
            if 'cookie' in kwargs and kwargs['cookie']:
                cookie_path = Path(kwargs['cookie'])
            else:
                cookie_path = self._get_douyin_cookie_path()
            
            # 执行下载
            loop = asyncio.get_event_loop()
            
            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([resolved_url])
                    # 获取实际输出文件名
                    info_dict = ydl.extract_info(resolved_url, download=False)
                    filename = ydl.prepare_filename(info_dict)
                    return filename
            
            with cookiefile_for_ytdlp(cookie_path) as ytdlp_cookie_path:
                if ytdlp_cookie_path:
                    ydl_opts['cookiefile'] = str(ytdlp_cookie_path)
                    logger.info(f"Using Douyin cookies for download from: {cookie_path}")

                final_path = await loop.run_in_executor(None, _download)
            
            logger.info(f"Douyin/TikTok video downloaded: {final_path}")
            
            return {
                'status': 'success',
                'filename': final_path,
                'title': info['title'],
                'duration': info.get('duration', 0),
                'filesize': 0,  # 可以尝试获取实际文件大小
                'platform': info['platform'],
                'download_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error downloading Douyin/TikTok video: {e}")
            if progress_callback:
                await progress_callback({
                    'status': 'error',
                    'error': str(e)
                })
            raise Exception(f"Failed to download Douyin/TikTok video: {str(e)}")
    
    async def _resolve_short_url(self, url: str) -> str:
        """
        解析短链接重定向

        Args:
            url: 原始URL（可能是短链接）

        Returns:
            解析后的完整URL
        """
        # 如果是短链接，需要解析
        if 'v.douyin.com' in url.lower():
            # 检查缓存
            if url in self._url_cache:
                logger.info(f"[CACHE HIT] Using cached URL for: {url}")
                return self._url_cache[url]

            try:
                import httpx
                logger.info(f"[NEW CODE 8.0] Attempting to resolve short URL: {url}")

                # 使用完整的浏览器请求头，模拟真实浏览器访问
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://www.douyin.com/',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                }

                # 使用 GET 请求代替 HEAD，因为抖音对 HEAD 请求返回 404
                async with httpx.AsyncClient(follow_redirects=True, timeout=5.0, headers=headers) as client:
                    response = await client.get(url)
                    resolved_url = str(response.url)
                    # 缓存解析结果
                    self._url_cache[url] = resolved_url
                    logger.info(f"[NEW CODE 8.0] Resolved short URL: {url} -> {resolved_url}")
                    logger.info(f"[NEW CODE 8.0] Response status: {response.status_code}")
                    return resolved_url
            except ImportError as ie:
                logger.error(f"[NEW CODE 8.0] httpx module not found: {ie}")
                raise Exception(f"缺少 httpx 依赖模块，请重新安装依赖: pip install httpx")
            except Exception as e:
                logger.error(f"[NEW CODE 8.0] Failed to resolve short URL: {type(e).__name__}: {e}")
                # 对于短链接，必须解析成功，否则抛出异常
                raise Exception(f"无法解析抖音短链接: {str(e)}")

        return url
    
    def _parse_formats(self, formats: list) -> list:
        """解析可用格式"""
        parsed_formats = []
        for fmt in formats:
            parsed_formats.append({
                'format_id': fmt.get('format_id'),
                'ext': fmt.get('ext'),
                'quality': fmt.get('format_note', 'unknown'),
                'filesize': fmt.get('filesize'),
                'width': fmt.get('width'),
                'height': fmt.get('height'),
                'fps': fmt.get('fps'),
            })
        return parsed_formats
    
    def _get_format_selector(self, quality: str, output_format: str) -> str:
        """
        根据质量要求构建格式选择器

        Args:
            quality: 质量级别
            output_format: 输出格式
        """
        if quality == 'audio':
            return 'bestaudio/best'
        elif quality == 'best':
            # 修复：移除格式限制，优先选择最佳质量
            return 'bestvideo+bestaudio/best'
        else:
            # 尝试匹配指定分辨率
            height = quality.rstrip('p')
            # 修复：移除格式限制，优化回退逻辑
            return f'bestvideo[height<={height}]+bestaudio/bestvideo[height<={height}]/best'
    
    def _create_progress_hook(self, callback: Callable, loop):
        """创建进度回调钩子"""
        def hook(d):
            if d['status'] == 'downloading':
                try:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0:
                        percentage = (downloaded / total) * 100
                        speed = d.get('speed', 0)
                        eta = d.get('eta', 0)
                        
                        # 使用 run_coroutine_threadsafe 从非事件循环线程调度协程
                        asyncio.run_coroutine_threadsafe(
                            callback({
                                'status': 'downloading',
                                'percentage': round(percentage, 2),
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
                    callback({
                        'status': 'finished',
                        'percentage': 100.0,
                        'message': 'Download completed, processing...'
                    }),
                    loop
                )
        
        return hook
    
    def _get_douyin_cookie_path(self) -> Optional[Path]:
        """获取抖音 Cookie 文件路径"""
        base_dir = Path(__file__).parent.parent.parent.parent
        cookie_dir = base_dir / "data" / "cookies"
        cookie_file = cookie_dir / "douyin_cookies.txt"

        if cookie_file.exists():
            return cookie_file

        tiktok_cookie_file = cookie_dir / "tiktok_cookies.txt"
        if tiktok_cookie_file.exists():
            return tiktok_cookie_file

        return None

    def _get_or_extract_cookies(self) -> Optional[Path]:
        """获取或从浏览器提取 Cookie"""
        # 先检查已有的 Cookie 文件
        cookie_path = self._get_douyin_cookie_path()
        if cookie_path and cookie_path.exists():
            return cookie_path

        # 尝试从浏览器提取
        try:
            import browser_cookie3
            base_dir = Path(__file__).parent.parent.parent.parent
            cookie_dir = base_dir / "data" / "cookies"
            cookie_dir.mkdir(parents=True, exist_ok=True)
            cookie_file = cookie_dir / "douyin_cookies.txt"

            # 尝试多个浏览器
            for browser_name, browser_func in [
                ('Edge', browser_cookie3.edge),
                ('Chrome', browser_cookie3.chrome),
                ('Firefox', browser_cookie3.firefox)
            ]:
                try:
                    logger.info(f"Trying to extract cookies from {browser_name}...")
                    cookies = browser_func(domain_name='douyin.com')

                    # 转换为 Netscape 格式
                    lines = ["# Netscape HTTP Cookie File\n"]
                    for cookie in cookies:
                        lines.append(
                            f"{cookie.domain}\tTRUE\t{cookie.path}\t"
                            f"{'TRUE' if cookie.secure else 'FALSE'}\t"
                            f"{cookie.expires or 0}\t{cookie.name}\t{cookie.value}\n"
                        )
                    write_cookie_file(cookie_file, "".join(lines))

                    logger.info(f"Successfully extracted cookies from {browser_name}")
                    return cookie_file
                except Exception as e:
                    logger.debug(f"Failed to extract from {browser_name}: {e}")
                    continue

            logger.warning("Failed to extract cookies from any browser")
        except ImportError:
            logger.debug("browser_cookie3 not installed, skipping auto-extraction")
        except Exception as e:
            logger.warning(f"Cookie extraction failed: {e}")

        return None
