"""
爱奇艺专用下载器
使用 Playwright 绕过爱奇艺的反爬虫机制
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
import httpx

from src.core.cookie_storage import cookiefile_for_ytdlp
from .base_downloader import BaseDownloader
from .douyin_downloader import check_playwright_available, auto_install_playwright

logger = logging.getLogger(__name__)


class IqiyiDownloader(BaseDownloader):
    """爱奇艺专用下载器"""

    def __init__(self, output_dir: str = None):
        super().__init__(output_dir)
        self.platform_name = "iqiyi"

    @staticmethod
    def supports_url(url: str) -> bool:
        """检查是否支持该URL"""
        url_lower = url.lower()
        return 'iqiyi.com' in url_lower

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取爱奇艺视频信息"""
        try:
            logger.info(f"[IqiyiDownloader] get_video_info called for: {url}")

            # 检查缓存
            cached_info = self._get_cached_info(url)
            if cached_info:
                logger.debug(f"Using cached info for: {url}")
                return cached_info

            # 使用 Playwright 获取视频信息
            video_data = await self._get_video_info_with_playwright(url)

            if not video_data:
                raise Exception("无法获取视频信息，爱奇艺可能需要登录或该视频不可用")

            # 缓存结果
            self._cache_info(url, video_data)

            return video_data

        except Exception as e:
            error_str = str(e)
            logger.error(f"Error extracting iQiyi video info: {e}")

            if "Playwright" in error_str:
                raise Exception(error_str)
            elif "timeout" in error_str.lower():
                raise Exception(f"获取视频信息超时，请检查网络连接")
            elif "drm" in error_str.lower():
                raise Exception(f"该视频有 DRM 保护，无法下载")
            else:
                raise Exception(f"获取爱奇艺视频信息失败: {error_str}")

    async def _get_video_info_with_playwright(self, url: str, retry_after_install: bool = True) -> Optional[Dict]:
        """使用 Playwright 获取视频信息"""
        # 检查 Playwright 是否可用
        available, error_code = await check_playwright_available()
        logger.info(f"[IqiyiDownloader] Playwright check: available={available}, error_code={error_code}")

        if not available:
            if error_code in ("playwright_not_installed", "chromium_not_installed") and retry_after_install:
                logger.info(f"[IqiyiDownloader] Playwright not available ({error_code}), attempting auto-install...")
                install_result = await auto_install_playwright()

                if install_result.get("success"):
                    logger.info("[IqiyiDownloader] Playwright auto-installed, retrying...")
                    return await self._get_video_info_with_playwright(url, retry_after_install=False)
                else:
                    error_msg = install_result.get("error", "Playwright 自动安装失败")
                    raise Exception(f"Playwright 未安装且自动安装失败: {error_msg}")
            else:
                error_messages = {
                    "playwright_not_installed": "Playwright 未安装，请在设置中安装 Playwright",
                    "chromium_not_installed": "Chromium 浏览器未安装，请在设置中安装 Playwright",
                }
                raise Exception(error_messages.get(error_code, f"Playwright 不可用: {error_code}"))

        from playwright.async_api import async_playwright

        logger.info(f"[Playwright] Fetching iQiyi video info for: {url}")

        # 设置浏览器路径
        browser_exe_path = self._find_browser_executable()

        # 获取 Cookie
        cookie_path = self._get_iqiyi_cookie_path()
        cookies = []

        if cookie_path:
            with cookiefile_for_ytdlp(cookie_path) as decrypted_path:
                if decrypted_path and Path(decrypted_path).exists():
                    cookies = self._load_cookies_for_playwright(str(decrypted_path))
                    logger.info(f"[Playwright] Loaded {len(cookies)} cookies")

        video_data = None
        video_urls = []

        async with async_playwright() as p:
            launch_options = {"headless": True}
            if browser_exe_path:
                launch_options["executable_path"] = browser_exe_path

            browser = await p.chromium.launch(**launch_options)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
            )

            if cookies:
                await context.add_cookies(cookies)

            page = await context.new_page()

            # 监听网络请求，捕获视频流 URL
            async def handle_response(response):
                nonlocal video_urls
                url_lower = response.url.lower()
                # 爱奇艺视频流 URL 特征
                if any(pattern in url_lower for pattern in ['.m3u8', '.mp4', 'cache.video.iqiyi.com', 'data.video.iqiyi.com']):
                    if response.status == 200:
                        video_urls.append(response.url)
                        logger.info(f"[Playwright] Captured video URL: {response.url[:100]}...")

            page.on('response', handle_response)

            try:
                # 访问页面
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)

                # 等待页面加载
                await asyncio.sleep(3)

                # 尝试从页面提取视频信息
                page_info = await page.evaluate('''() => {
                    const result = {
                        title: '',
                        duration: 0,
                        thumbnail: '',
                        description: '',
                    };

                    // 尝试获取标题
                    const titleEl = document.querySelector('h1.title') ||
                                   document.querySelector('.player-title') ||
                                   document.querySelector('title');
                    if (titleEl) {
                        result.title = titleEl.textContent.trim().replace(/_.*$/, '').replace(/-.*爱奇艺$/, '');
                    }

                    // 尝试获取封面
                    const posterEl = document.querySelector('video[poster]') ||
                                    document.querySelector('.iqp-player video');
                    if (posterEl && posterEl.poster) {
                        result.thumbnail = posterEl.poster;
                    }

                    // 尝试获取视频元素
                    const videoEl = document.querySelector('video');
                    if (videoEl && videoEl.duration) {
                        result.duration = videoEl.duration;
                    }

                    // 尝试获取描述
                    const descEl = document.querySelector('.intro-text') ||
                                  document.querySelector('.desc');
                    if (descEl) {
                        result.description = descEl.textContent.trim();
                    }

                    return result;
                }''')

                # 等待更多视频 URL 被捕获
                await asyncio.sleep(2)

                # 如果没有捕获到视频 URL，尝试点击播放按钮
                if not video_urls:
                    try:
                        play_btn = await page.query_selector('.iqp-btn-play, .play-btn, [class*="play"]')
                        if play_btn:
                            await play_btn.click()
                            await asyncio.sleep(3)
                    except:
                        pass

                # 构建视频信息
                video_data = {
                    'title': page_info.get('title') or '爱奇艺视频',
                    'url': url,
                    'duration': page_info.get('duration', 0),
                    'thumbnail': page_info.get('thumbnail', ''),
                    'description': page_info.get('description', ''),
                    'uploader': '爱奇艺',
                    'platform': 'iqiyi',
                    'formats': [],
                    'video_urls': video_urls,
                }

                # 如果捕获到视频 URL，添加格式信息
                if video_urls:
                    for i, vurl in enumerate(video_urls[:5]):  # 最多保留5个
                        video_data['formats'].append({
                            'format_id': f'stream_{i}',
                            'ext': 'mp4' if '.mp4' in vurl else 'm3u8',
                            'url': vurl,
                        })

            except Exception as e:
                logger.warning(f"[Playwright] Page load warning: {e}")

            await browser.close()

        # 检查是否获取到有效信息
        if video_data and (video_data.get('title') or video_urls):
            return video_data

        return None

    def _find_browser_executable(self) -> Optional[str]:
        """查找浏览器可执行文件"""
        if sys.platform == 'win32':
            user_pw_path = Path.home() / 'AppData' / 'Local' / 'ms-playwright'
        elif sys.platform == 'darwin':
            user_pw_path = Path.home() / 'Library' / 'Caches' / 'ms-playwright'
        else:
            user_pw_path = Path.home() / '.cache' / 'ms-playwright'

        if not user_pw_path.exists():
            return None

        chromium_patterns = ['chromium_headless_shell-*', 'chromium-*']
        for pattern in chromium_patterns:
            chromium_dirs = list(user_pw_path.glob(pattern))
            if chromium_dirs:
                chromium_dir = sorted(chromium_dirs, reverse=True)[0]

                if sys.platform == 'win32':
                    possible_exes = [
                        chromium_dir / 'chrome-headless-shell-win64' / 'chrome-headless-shell.exe',
                        chromium_dir / 'chrome-win64' / 'chrome.exe',
                    ]
                elif sys.platform == 'darwin':
                    possible_exes = [
                        chromium_dir / 'chrome-headless-shell-mac-arm64' / 'chrome-headless-shell',
                        chromium_dir / 'chrome-headless-shell-mac' / 'chrome-headless-shell',
                    ]
                else:
                    possible_exes = [
                        chromium_dir / 'chrome-headless-shell-linux' / 'chrome-headless-shell',
                        chromium_dir / 'chrome-linux' / 'chrome',
                    ]

                for exe_path in possible_exes:
                    if exe_path.exists():
                        return str(exe_path)

        return None

    def _load_cookies_for_playwright(self, cookie_path: str) -> list:
        """从 Netscape 格式文件加载 Cookie"""
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

    def _get_iqiyi_cookie_path(self) -> Optional[Path]:
        """获取爱奇艺 Cookie 文件路径"""
        from .cookie_manager import get_cookie_base_dir
        cookie_dir = get_cookie_base_dir()
        cookie_file = cookie_dir / "iqiyi_cookies.txt"

        if cookie_file.exists():
            logger.info(f"[IqiyiDownloader] Found iqiyi cookie: {cookie_file}")
            return cookie_file

        return None

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
        """下载爱奇艺视频"""
        try:
            # 获取视频信息
            info = await self.get_video_info(url)

            video_urls = info.get('video_urls', [])
            if not video_urls:
                raise Exception("无法获取视频下载地址，该视频可能有 DRM 保护或需要 VIP")

            # 选择视频 URL（优先 mp4）
            video_url = None
            for vurl in video_urls:
                if '.mp4' in vurl.lower():
                    video_url = vurl
                    break
            if not video_url:
                video_url = video_urls[0]

            # 检查是否是 m3u8
            if '.m3u8' in video_url.lower():
                raise Exception("该视频使用 HLS 流媒体格式，暂不支持直接下载。建议使用其他工具下载 m3u8 视频。")

            # 构建文件名
            safe_title = self._sanitize_filename(info['title'])
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"{safe_title}_{timestamp}.mp4"
            actual_output_path = output_path or str(self.output_dir)
            full_output_path = Path(actual_output_path) / output_filename

            full_output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"[IqiyiDownloader] Downloading video to: {full_output_path}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.iqiyi.com/',
            }

            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=300) as client:
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

            logger.info(f"[IqiyiDownloader] Download completed: {full_output_path}")

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
                'platform': 'iqiyi',
                'download_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error downloading iQiyi video: {e}")
            if progress_callback:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(e)
                })
            raise Exception(f"下载失败: {str(e)}")
