"""
抖音/TikTok 专用下载器
针对抖音和TikTok平台优化，处理短链接和反爬虫机制
使用 Playwright 绕过抖音的反爬虫签名验证
"""
import asyncio
import logging
import os
import re
import json
import sys
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
import httpx

from src.core.cookie_storage import cookiefile_for_ytdlp, write_cookie_file
from .base_downloader import BaseDownloader
from .proxy_config import get_proxy_url

logger = logging.getLogger(__name__)

# Playwright 可用状态缓存
_playwright_available: Optional[bool] = None
_playwright_error_code: Optional[str] = None  # 缓存错误码
# Playwright 安装锁，防止并发安装
_playwright_install_lock: Optional[asyncio.Lock] = None


def reset_playwright_cache():
    """重置 Playwright 可用状态缓存（安装后调用）"""
    global _playwright_available, _playwright_error_code
    _playwright_available = None
    _playwright_error_code = None
    logger.info("[Playwright] Cache reset")


def check_playwright_available() -> tuple:
    """
    检查 Playwright 是否可用（延迟检查，不在模块导入时执行）
    
    Returns:
        (是否可用, 错误码)
        错误码: "" (可用), "playwright_not_installed", "chromium_not_installed", "check_failed:xxx"
    """
    global _playwright_available, _playwright_error_code
    import sys
    
    # 使用缓存
    if _playwright_available is not None:
        if _playwright_available:
            return True, ""
        else:
            return False, _playwright_error_code or "playwright_not_installed"
    
    # 检查 Playwright 包（延迟导入）
    try:
        import playwright
        from playwright.sync_api import sync_playwright
    except ImportError:
        _playwright_available = False
        _playwright_error_code = "playwright_not_installed"
        return False, "playwright_not_installed"
    
    # 检查 Chromium 浏览器 - 需要检查多个可能的位置
    try:
        # 可能的浏览器路径列表
        possible_browser_paths = []
        
        # 1. 用户目录（标准安装位置）
        if sys.platform == 'win32':
            user_pw_path = Path.home() / 'AppData' / 'Local' / 'ms-playwright'
        elif sys.platform == 'darwin':
            user_pw_path = Path.home() / 'Library' / 'Caches' / 'ms-playwright'
        else:
            user_pw_path = Path.home() / '.cache' / 'ms-playwright'
        possible_browser_paths.append(user_pw_path)
        
        # 2. 打包环境中 Playwright 的 .local-browsers 目录
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后的路径
            if hasattr(sys, '_MEIPASS'):
                internal_path = Path(sys._MEIPASS)
            else:
                internal_path = Path(sys.executable).parent / '_internal'
            
            # Playwright driver 的 .local-browsers 目录
            playwright_local = internal_path / 'playwright' / 'driver' / 'package' / '.local-browsers'
            possible_browser_paths.append(playwright_local)
            logger.debug(f"[Playwright] Packaged env, checking: {playwright_local}")
        
        logger.info(f"[Playwright] Checking browser paths: {possible_browser_paths}")
        
        # 检查每个可能的路径
        for pw_browsers_path in possible_browser_paths:
            logger.info(f"[Playwright] Checking path: {pw_browsers_path}, exists: {pw_browsers_path.exists()}")
            if not pw_browsers_path.exists():
                continue
                
            # 查找 chromium_headless_shell 或 chromium 目录
            # 优先检查 chromium_headless_shell，因为这是我们默认安装的（更小）
            chromium_patterns = ['chromium_headless_shell-*', 'chromium-*']
            for pattern in chromium_patterns:
                chromium_dirs = list(pw_browsers_path.glob(pattern))
                logger.info(f"[Playwright] Pattern {pattern} found dirs: {chromium_dirs}")
                if chromium_dirs:
                    chromium_dir = sorted(chromium_dirs, reverse=True)[0]
                    
                    # 查找可执行文件 - 支持多种目录结构
                    chrome_exe = None
                    if sys.platform == 'win32':
                        possible_exes = [
                            chromium_dir / 'chrome-headless-shell-win64' / 'chrome-headless-shell.exe',
                            chromium_dir / 'chrome-win64' / 'chrome.exe',
                            chromium_dir / 'chrome-win' / 'chrome.exe',
                        ]
                    elif sys.platform == 'darwin':
                        possible_exes = [
                            chromium_dir / 'chrome-headless-shell-mac-arm64' / 'chrome-headless-shell',
                            chromium_dir / 'chrome-headless-shell-mac' / 'chrome-headless-shell',
                            chromium_dir / 'chrome-mac' / 'Chromium.app' / 'Contents' / 'MacOS' / 'Chromium',
                            chromium_dir / 'chrome-mac-arm64' / 'Chromium.app' / 'Contents' / 'MacOS' / 'Chromium',
                        ]
                    else:
                        possible_exes = [
                            chromium_dir / 'chrome-headless-shell-linux' / 'chrome-headless-shell',
                            chromium_dir / 'chrome-linux' / 'chrome',
                        ]
                    
                    for exe_path in possible_exes:
                        logger.info(f"[Playwright] Checking exe: {exe_path}, exists: {exe_path.exists()}")
                        if exe_path.exists():
                            chrome_exe = exe_path
                            break
                    
                    if chrome_exe:
                        _playwright_available = True
                        _playwright_error_code = ""
                        logger.info(f"[Playwright] Available and ready: {chrome_exe}")
                        return True, ""
        
        logger.info(f"[Playwright] Chromium not found in any of: {possible_browser_paths}")
        _playwright_available = False
        _playwright_error_code = "chromium_not_installed"
        return False, "chromium_not_installed"
        
    except Exception as e:
        logger.error(f"[Playwright] Check failed: {e}")
        _playwright_available = False
        _playwright_error_code = f"check_failed:{str(e)}"
        return False, f"check_failed:{str(e)}"


async def auto_install_playwright(progress_callback: Optional[Callable] = None) -> dict:
    """
    自动安装 Playwright 和 Chromium 浏览器
    
    Args:
        progress_callback: 进度回调函数 callback(percent, message)
    
    Returns:
        dict: {"success": bool, "message": str, "error": str}
    """
    global _playwright_install_lock
    
    if _playwright_install_lock is None:
        _playwright_install_lock = asyncio.Lock()
    
    async with _playwright_install_lock:
        try:
            from src.core.tool_manager import get_tool_manager
            
            tool_mgr = get_tool_manager()
            
            logger.info("[Playwright] Starting auto-installation...")
            
            result = await tool_mgr.install_playwright(progress_callback)
            
            if result.get("success"):
                # 重置缓存，下次检查会重新验证
                reset_playwright_cache()
                logger.info("[Playwright] Auto-installation completed successfully")
            else:
                logger.error(f"[Playwright] Auto-installation failed: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"[Playwright] Auto-installation error: {e}")
            return {
                "success": False,
                "error": f"自动安装失败: {str(e)}"
            }


class DouyinDownloader(BaseDownloader):
    """抖音/TikTok 专用下载器"""

    def __init__(self, output_dir: str = "./data/downloads"):
        super().__init__(output_dir)
        self.platform_name = "douyin"
        self._url_cache = {}  # 短链接缓存
        self._video_info_cache = {}  # 视频信息缓存
    
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
            logger.info(f"[DouyinDownloader] get_video_info called for: {url}")

            # 检查缓存
            cached_info = self._get_cached_info(url)
            if cached_info:
                logger.debug(f"Using cached info for: {url}")
                return cached_info

            # 处理短链接重定向
            resolved_url = await self._resolve_short_url(url)
            logger.info(f"[DouyinDownloader] Resolved URL: {resolved_url}")
            
            # 使用 Playwright 获取视频信息（支持自动安装）
            video_data = await self._get_video_info_with_playwright(resolved_url)
            
            if not video_data:
                raise Exception("无法获取视频信息，请确保已配置有效的抖音 Cookie")
            
            # 解析视频信息
            result = self._parse_video_data(video_data, resolved_url)
            
            # 缓存结果
            self._cache_info(url, result)
            
            return result
        except Exception as e:
            error_str = str(e)
            logger.error(f"Error extracting Douyin/TikTok video info: {e}")
            
            # 提供更友好的中文错误消息
            if "Playwright" in error_str:
                raise Exception(error_str)  # 已经是中文消息
            elif "timeout" in error_str.lower():
                raise Exception(f"获取视频信息超时，请检查网络连接")
            elif "cookie" in error_str.lower():
                raise Exception(f"Cookie 无效或已过期，请重新配置抖音 Cookie")
            else:
                raise Exception(f"获取视频信息失败: {error_str}")
    
    async def _get_video_info_with_playwright(self, url: str, retry_after_install: bool = True) -> Optional[Dict]:
        """
        使用 Playwright 获取视频信息
        
        Args:
            url: 视频 URL
            retry_after_install: 如果 Playwright 未安装，是否自动安装后重试
        """
        # 检查 Playwright 是否可用
        available, error_code = check_playwright_available()
        logger.info(f"[DouyinDownloader] Playwright check: available={available}, error_code={error_code}")
        
        if not available:
            # 根据错误码决定是否尝试自动安装
            if error_code in ("playwright_not_installed", "chromium_not_installed") and retry_after_install:
                logger.info(f"[DouyinDownloader] Playwright not available ({error_code}), attempting auto-install...")
                
                # 尝试自动安装
                install_result = await auto_install_playwright()
                
                if install_result.get("success"):
                    logger.info("[DouyinDownloader] Playwright auto-installed, retrying...")
                    # 安装成功，重试获取视频信息（不再重试安装）
                    return await self._get_video_info_with_playwright(url, retry_after_install=False)
                else:
                    # 安装失败
                    error_msg = install_result.get("error", "Playwright 自动安装失败")
                    raise Exception(f"Playwright 未安装且自动安装失败: {error_msg}")
            else:
                # 不支持自动安装或已经重试过
                error_messages = {
                    "playwright_not_installed": "Playwright 未安装，请在设置中安装 Playwright",
                    "chromium_not_installed": "Chromium 浏览器未安装，请在设置中安装 Playwright",
                }
                if error_code.startswith("check_failed:"):
                    raise Exception(f"Playwright 检查失败: {error_code[13:]}")
                raise Exception(error_messages.get(error_code, f"Playwright 不可用: {error_code}"))
        
        from playwright.async_api import async_playwright
        
        logger.info(f"[Playwright] Fetching video info for: {url}")
        
        # 设置 PLAYWRIGHT_BROWSERS_PATH 环境变量，确保 Playwright 能找到用户目录中安装的浏览器
        # 这在打包环境中尤其重要，因为 Playwright 默认会查找内部的 .local-browsers 目录
        if sys.platform == 'win32':
            user_pw_path = Path.home() / 'AppData' / 'Local' / 'ms-playwright'
        elif sys.platform == 'darwin':
            user_pw_path = Path.home() / 'Library' / 'Caches' / 'ms-playwright'
        else:
            user_pw_path = Path.home() / '.cache' / 'ms-playwright'
        
        if user_pw_path.exists():
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(user_pw_path)
            logger.info(f"[Playwright] Set PLAYWRIGHT_BROWSERS_PATH to: {user_pw_path}")
        
        # 查找可用的浏览器可执行文件
        # Playwright 1.49+ 默认使用 chromium_headless_shell，但用户可能安装的是 chromium
        # 我们需要找到实际存在的浏览器并指定 executable_path
        browser_exe_path = None
        if user_pw_path.exists():
            # 按优先级查找浏览器
            chromium_patterns = ['chromium_headless_shell-*', 'chromium-*']
            for pattern in chromium_patterns:
                chromium_dirs = list(user_pw_path.glob(pattern))
                if chromium_dirs:
                    chromium_dir = sorted(chromium_dirs, reverse=True)[0]
                    
                    if sys.platform == 'win32':
                        possible_exes = [
                            chromium_dir / 'chrome-headless-shell-win64' / 'chrome-headless-shell.exe',
                            chromium_dir / 'chrome-win64' / 'chrome.exe',
                            chromium_dir / 'chrome-win' / 'chrome.exe',
                        ]
                    elif sys.platform == 'darwin':
                        possible_exes = [
                            chromium_dir / 'chrome-headless-shell-mac-arm64' / 'chrome-headless-shell',
                            chromium_dir / 'chrome-headless-shell-mac' / 'chrome-headless-shell',
                            chromium_dir / 'chrome-mac-arm64' / 'Chromium.app' / 'Contents' / 'MacOS' / 'Chromium',
                            chromium_dir / 'chrome-mac' / 'Chromium.app' / 'Contents' / 'MacOS' / 'Chromium',
                        ]
                    else:
                        possible_exes = [
                            chromium_dir / 'chrome-headless-shell-linux' / 'chrome-headless-shell',
                            chromium_dir / 'chrome-linux' / 'chrome',
                        ]
                    
                    for exe_path in possible_exes:
                        if exe_path.exists():
                            browser_exe_path = str(exe_path)
                            logger.info(f"[Playwright] Found browser executable: {browser_exe_path}")
                            break
                    
                    if browser_exe_path:
                        break
        
        # 获取 Cookie
        cookie_path = self._get_douyin_cookie_path()
        cookies = []
        
        if cookie_path:
            with cookiefile_for_ytdlp(cookie_path) as decrypted_path:
                if decrypted_path and Path(decrypted_path).exists():
                    cookies = self._load_cookies_for_playwright(str(decrypted_path))
                    logger.info(f"[Playwright] Loaded {len(cookies)} cookies")
        
        video_data = None
        
        async with async_playwright() as p:
            # 使用找到的浏览器可执行文件路径，解决版本不匹配问题
            launch_options = {"headless": True}
            if browser_exe_path:
                launch_options["executable_path"] = browser_exe_path
                logger.info(f"[Playwright] Launching with executable_path: {browser_exe_path}")
            
            browser = await p.chromium.launch(**launch_options)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
            )
            
            if cookies:
                await context.add_cookies(cookies)
            
            page = await context.new_page()
            
            # 监听 API 响应
            async def handle_response(response):
                nonlocal video_data
                if 'aweme/v1/web/aweme/detail' in response.url:
                    try:
                        data = await response.json()
                        if 'aweme_detail' in data and data['aweme_detail']:
                            video_data = data
                            logger.info("[Playwright] Captured API response!")
                    except:
                        pass
            
            page.on('response', handle_response)
            
            try:
                # 访问页面，等待网络空闲或超时
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                
                # 等待 API 响应
                for _ in range(10):  # 最多等待 5 秒
                    if video_data:
                        break
                    await asyncio.sleep(0.5)
                
                # 如果没有捕获到 API 响应，尝试从页面提取
                if not video_data:
                    render_data = await page.evaluate('''() => {
                        const script = document.getElementById('RENDER_DATA');
                        if (script) {
                            return decodeURIComponent(script.textContent);
                        }
                        return null;
                    }''')
                    
                    if render_data:
                        try:
                            data = json.loads(render_data)
                            video_detail = data.get('app', {}).get('videoDetail')
                            if video_detail:
                                video_data = {'aweme_detail': video_detail}
                        except:
                            pass
                
            except Exception as e:
                logger.warning(f"[Playwright] Page load warning: {e}")
            
            await browser.close()
        
        return video_data
    
    def _load_cookies_for_playwright(self, cookie_path: str) -> list:
        """从 Netscape 格式文件加载 Cookie 为 Playwright 格式"""
        cookies = []
        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('\t')
                        if len(parts) >= 7:
                            domain, _, path, secure, expires, name, value = parts[:7]
                            if name:
                                cookies.append({
                                    'name': name,
                                    'value': value,
                                    'domain': domain if domain.startswith('.') else f'.{domain}',
                                    'path': path,
                                    'secure': secure.upper() == 'TRUE',
                                    'httpOnly': False,
                                })
        except Exception as e:
            logger.warning(f"Failed to load cookies: {e}")
        return cookies
    
    def _parse_video_data(self, video_data: Dict, url: str) -> Dict[str, Any]:
        """解析视频数据"""
        detail = video_data.get('aweme_detail', {})
        
        # 提取视频 URL
        video_urls = []
        video_info = detail.get('video', {})
        
        # 尝试从 bit_rate 获取最高质量
        bit_rates = video_info.get('bit_rate', [])
        if bit_rates:
            # 按比特率排序，选择最高的
            sorted_rates = sorted(bit_rates, key=lambda x: x.get('bit_rate', 0), reverse=True)
            for rate in sorted_rates:
                play_addr = rate.get('play_addr', {})
                urls = play_addr.get('url_list', [])
                if urls:
                    video_urls.extend(urls)
                    break
        
        # 备用：从 play_addr 获取
        if not video_urls:
            play_addr = video_info.get('play_addr', {})
            video_urls = play_addr.get('url_list', [])
        
        # 提取封面
        cover = video_info.get('cover', {})
        thumbnail = None
        if cover:
            cover_urls = cover.get('url_list', [])
            if cover_urls:
                thumbnail = cover_urls[0]
        
        # 提取作者信息
        author = detail.get('author', {})
        
        # 提取统计信息
        statistics = detail.get('statistics', {})
        
        # 构建格式列表
        formats = []
        for rate in bit_rates:
            play_addr = rate.get('play_addr', {})
            formats.append({
                'format_id': rate.get('gear_name', 'unknown'),
                'ext': rate.get('format', 'mp4'),
                'quality': f"{play_addr.get('height', 0)}p",
                'filesize': play_addr.get('data_size'),
                'width': play_addr.get('width'),
                'height': play_addr.get('height'),
                'fps': rate.get('FPS'),
                'bitrate': rate.get('bit_rate'),
            })
        
        return {
            'title': detail.get('desc', 'Unknown'),
            'url': url,
            'duration': detail.get('duration', 0) / 1000 if detail.get('duration') else 0,  # 毫秒转秒
            'thumbnail': thumbnail,
            'uploader': author.get('nickname'),
            'uploader_id': author.get('uid'),
            'upload_date': detail.get('create_time'),
            'view_count': statistics.get('play_count', 0),
            'like_count': statistics.get('digg_count', 0),
            'comment_count': statistics.get('comment_count', 0),
            'collect_count': statistics.get('collect_count', 0),
            'share_count': statistics.get('share_count', 0),
            'description': detail.get('desc', ''),
            'formats': formats,
            'video_urls': video_urls,
            'platform': 'tiktok' if 'tiktok.com' in url else 'douyin',
            'raw_info': detail
        }
    
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
        """下载抖音/TikTok视频"""
        try:
            # 获取视频信息
            info = await self.get_video_info(url)
            
            if not info.get('video_urls'):
                raise Exception("无法获取视频下载地址")
            
            # 选择视频 URL
            video_url = info['video_urls'][0]
            
            # 确定输出格式
            output_format = 'mp4'
            if format_id:
                fid = str(format_id).strip().lower()
                if fid in ('mp4', 'mkv', 'webm', 'mp3'):
                    output_format = fid
            
            # 构建安全的文件名
            safe_title = self._sanitize_filename(info['title'])
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"{safe_title}_{timestamp}.{output_format}"
            actual_output_path = output_path or str(self.output_dir)
            full_output_path = Path(actual_output_path) / output_filename
            
            # 确保输出目录存在
            full_output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 下载视频
            logger.info(f"[DouyinDownloader] Downloading video to: {full_output_path}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Referer': 'https://www.douyin.com/',
            }
            
            # TikTok 需要代理，抖音不需要
            proxy_url = get_proxy_url() if 'tiktok.com' in url.lower() else None
            
            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=300, proxy=proxy_url) as client:
                async with client.stream('GET', video_url) as response:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    start_time = datetime.now()
                    last_downloaded = 0
                    last_time = start_time
                    
                    with open(full_output_path, 'wb') as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback and total_size > 0:
                                current_time = datetime.now()
                                time_diff = (current_time - last_time).total_seconds()
                                
                                # 计算速度（每0.5秒更新一次）
                                if time_diff >= 0.5:
                                    bytes_diff = downloaded - last_downloaded
                                    speed = bytes_diff / time_diff if time_diff > 0 else 0
                                    last_downloaded = downloaded
                                    last_time = current_time
                                else:
                                    speed = 0
                                
                                # 计算 ETA
                                remaining = total_size - downloaded
                                eta = int(remaining / speed) if speed > 0 else 0
                                
                                percentage = (downloaded / total_size) * 100
                                await progress_callback({
                                    'task_id': task_id,
                                    'status': 'downloading',
                                    'progress': round(percentage, 2),
                                    'downloaded': downloaded,
                                    'total': total_size,
                                    'speed': speed,
                                    'eta': eta,
                                })
            
            logger.info(f"[DouyinDownloader] Download completed: {full_output_path}")
            
            if progress_callback:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'finished',
                    'progress': 100.0,
                    'filename': str(full_output_path),
                })
            
            return {
                'status': 'success',
                'filename': str(full_output_path),
                'title': info['title'],
                'duration': info.get('duration', 0),
                'filesize': full_output_path.stat().st_size if full_output_path.exists() else 0,
                'platform': info['platform'],
                'download_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error downloading Douyin/TikTok video: {e}")
            if progress_callback:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(e)
                })
            raise Exception(f"下载失败: {str(e)}")
    
    async def _resolve_short_url(self, url: str) -> str:
        """解析短链接重定向"""
        if 'v.douyin.com' in url.lower():
            if url in self._url_cache:
                return self._url_cache[url]

            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                }
                
                # TikTok 短链接需要代理
                proxy_url = get_proxy_url() if 'tiktok.com' in url.lower() else None

                async with httpx.AsyncClient(follow_redirects=True, timeout=10.0, headers=headers, proxy=proxy_url) as client:
                    response = await client.get(url)
                    resolved_url = str(response.url)
                    self._url_cache[url] = resolved_url
                    logger.info(f"[DouyinDownloader] Resolved short URL: {url} -> {resolved_url}")
                    return resolved_url
            except Exception as e:
                logger.error(f"[DouyinDownloader] Failed to resolve short URL: {e}")
                raise Exception(f"无法解析抖音短链接: {str(e)}")

        return url
    
    def _get_douyin_cookie_path(self) -> Optional[Path]:
        """获取抖音 Cookie 文件路径"""
        # 使用统一的 Cookie 目录获取函数（支持打包环境）
        from .cookie_manager import get_cookie_base_dir
        cookie_dir = get_cookie_base_dir()
        cookie_file = cookie_dir / "douyin_cookies.txt"

        logger.debug(f"[DouyinDownloader] Looking for cookie at: {cookie_file}")

        if cookie_file.exists():
            logger.info(f"[DouyinDownloader] Found douyin cookie: {cookie_file}")
            return cookie_file

        tiktok_cookie_file = cookie_dir / "tiktok_cookies.txt"
        if tiktok_cookie_file.exists():
            logger.info(f"[DouyinDownloader] Found tiktok cookie: {tiktok_cookie_file}")
            return tiktok_cookie_file

        logger.warning(f"[DouyinDownloader] No cookie file found in: {cookie_dir}")
        return None
