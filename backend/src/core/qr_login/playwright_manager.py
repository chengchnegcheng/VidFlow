"""
Playwright浏览器管理器

提供Playwright浏览器实例的创建、管理和资源清理功能。
用于需要模拟浏览器的平台扫码登录（如抖音、小红书、优酷）。
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

from .config import get_config

logger = logging.getLogger(__name__)


class PlaywrightManager:
    """Playwright浏览器管理器

    管理Playwright浏览器实例，提供：
    - 浏览器启动和关闭
    - Stealth脚本注入（防止检测）
    - 资源清理
    - 并发控制
    """

    # 最大同时运行的浏览器实例数
    MAX_CONCURRENT_BROWSERS = 2

    # Stealth脚本路径
    STEALTH_SCRIPT_PATH = Path(__file__).parent / "libs" / "stealth.min.js"

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._active_contexts: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_BROWSERS)

    async def _ensure_playwright(self):
        """确保Playwright已初始化"""
        if self._playwright is None:
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                logger.info("Playwright初始化成功")
            except Exception as e:
                logger.error(f"Playwright初始化失败: {e}")
                raise Exception(f"Playwright初始化失败: {e}")

    async def _ensure_browser(self):
        """确保浏览器已启动"""
        await self._ensure_playwright()

        if self._browser is None or not self._browser.is_connected():
            try:
                config = get_config()

                # 获取headless模式设置（Docker环境自动使用无头模式）
                headless = config.get_headless_mode()

                # 尝试使用系统已安装的Chrome（如果配置启用）
                chrome_path = None
                if config.USE_SYSTEM_CHROME:
                    chrome_path = self._find_chrome_executable()

                launch_options = {
                    'headless': headless,
                    'args': [
                        '--disable-blink-features=AutomationControlled',  # 禁用自动化控制特征
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',  # 允许跨域（某些平台需要）
                        '--disable-features=IsolateOrigins,site-per-process',
                        f'--window-size={config.BROWSER_WIDTH},{config.BROWSER_HEIGHT}',
                        '--start-maximized',
                        '--exclude-switches=enable-automation',
                        '--disable-infobars',
                    ]
                }

                # 如果找到系统Chrome，使用它
                if chrome_path:
                    launch_options['executable_path'] = chrome_path
                    logger.info(f"使用系统Chrome: {chrome_path}")
                else:
                    logger.info("使用Playwright内置Chromium")

                self._browser = await self._playwright.chromium.launch(**launch_options)
                mode_text = "无头模式" if headless else "有头模式"
                logger.info(f"浏览器启动成功（{mode_text}）")

                # 如果是Docker环境，给出提示
                if config.IS_DOCKER:
                    logger.warning("检测到Docker环境，已自动切换到无头模式")

            except Exception as e:
                logger.error(f"浏览器启动失败: {e}")
                raise Exception(f"浏览器启动失败: {e}")

    def _find_chrome_executable(self) -> Optional[str]:
        """查找系统已安装的Chrome浏览器路径"""
        import platform
        import os

        system = platform.system()
        possible_paths = []

        if system == "Windows":
            possible_paths = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]
        elif system == "Darwin":  # macOS
            possible_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ]
        elif system == "Linux":
            possible_paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
            ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    async def create_context(
        self,
        context_id: str,
        use_stealth: bool = True,
        extra_cookies: list = None,
        viewport: dict = None
    ):
        """创建新的浏览器上下文

        Args:
            context_id: 上下文唯一标识
            use_stealth: 是否使用stealth脚本
            extra_cookies: 额外的Cookie列表
            viewport: 视口大小配置

        Returns:
            BrowserContext实例
        """
        async with self._semaphore:
            async with self._lock:
                await self._ensure_browser()

                # 默认视口
                if viewport is None:
                    viewport = {'width': 1920, 'height': 1080}

                # 创建上下文
                context = await self._browser.new_context(
                    viewport=viewport,
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='zh-CN',
                    timezone_id='Asia/Shanghai',
                )

                # 注入stealth脚本
                if use_stealth:
                    await self._inject_stealth(context)

                # 添加额外Cookie
                if extra_cookies:
                    await context.add_cookies(extra_cookies)

                self._active_contexts[context_id] = context
                logger.info(f"创建浏览器上下文: {context_id}")

                return context

    async def _inject_stealth(self, context):
        """注入增强版stealth脚本防止检测

        Args:
            context: BrowserContext实例
        """
        # 增强版stealth脚本
        stealth_script = """
        // ========== 核心反检测 ==========

        // 1. 隐藏webdriver属性（最重要）
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });

        // 2. 覆盖navigator.plugins（模拟真实浏览器）
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                ];
                return plugins;
            }
        });

        // 3. 修改navigator.languages（中国用户特征）
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en-US', 'en']
        });

        // 4. 添加chrome对象（Chrome浏览器特征）
        if (!window.chrome) {
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        }

        // 5. 修改permissions.query（防止权限检测）
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );

        // 6. 隐藏所有自动化特征标记
        const automationKeys = [
            'cdc_adoQpoasnfa76pfcZLmcfl_Array',
            'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
            'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
            '__webdriver_script_fn',
            '__driver_evaluate',
            '__webdriver_evaluate',
            '__selenium_evaluate',
            '__fxdriver_evaluate',
            '__driver_unwrapped',
            '__webdriver_unwrapped',
            '__selenium_unwrapped',
            '__fxdriver_unwrapped',
            '__webdriver_script_func',
            '__webdriver_script_function'
        ];

        automationKeys.forEach(key => {
            delete window[key];
        });

        // 7. 修改navigator.maxTouchPoints（模拟触摸屏）
        Object.defineProperty(navigator, 'maxTouchPoints', {
            get: () => 1
        });

        // 8. 覆盖Function.prototype.toString（隐藏代理痕迹）
        const originalToString = Function.prototype.toString;
        Function.prototype.toString = function() {
            if (this === navigator.permissions.query) {
                return 'function query() { [native code] }';
            }
            return originalToString.call(this);
        };

        // 9. 添加真实的navigator.platform
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32'
        });

        // 10. 修改navigator.hardwareConcurrency（CPU核心数）
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8
        });

        // 11. 添加navigator.deviceMemory（设备内存）
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });

        // 12. 覆盖window.outerWidth/outerHeight（真实窗口大小）
        Object.defineProperty(window, 'outerWidth', {
            get: () => window.innerWidth
        });
        Object.defineProperty(window, 'outerHeight', {
            get: () => window.innerHeight + 85
        });

        // 13. 添加真实的screen属性
        Object.defineProperty(window.screen, 'availWidth', {
            get: () => 1920
        });
        Object.defineProperty(window.screen, 'availHeight', {
            get: () => 1040
        });

        // 14. 隐藏Playwright特征
        delete window.__playwright;
        delete window.__pw_manual;
        delete window.__PW_inspect;

        // 15. 覆盖Date.prototype.getTimezoneOffset（中国时区）
        const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
        Date.prototype.getTimezoneOffset = function() {
            return -480; // UTC+8 (中国时区)
        };

        console.log('[Stealth] 反检测脚本已注入');
        """

        # 尝试加载外部stealth脚本（如果存在）
        if self.STEALTH_SCRIPT_PATH.exists():
            try:
                external_script = self.STEALTH_SCRIPT_PATH.read_text(encoding='utf-8')
                stealth_script = external_script + "\n" + stealth_script
                logger.debug("已加载外部stealth脚本")
            except Exception as e:
                logger.warning(f"加载外部stealth脚本失败，使用内置脚本: {e}")

        await context.add_init_script(stealth_script)

    async def get_context(self, context_id: str):
        """获取已存在的上下文

        Args:
            context_id: 上下文唯一标识

        Returns:
            BrowserContext实例或None
        """
        return self._active_contexts.get(context_id)

    async def close_context(self, context_id: str):
        """关闭并清理上下文

        Args:
            context_id: 上下文唯一标识
        """
        async with self._lock:
            context = self._active_contexts.pop(context_id, None)
            if context:
                try:
                    await context.close()
                    logger.info(f"关闭浏览器上下文: {context_id}")
                except Exception as e:
                    logger.warning(f"关闭上下文失败: {e}")

    async def cleanup(self):
        """清理所有资源"""
        async with self._lock:
            # 关闭所有上下文
            for context_id, context in list(self._active_contexts.items()):
                try:
                    await context.close()
                except Exception as e:
                    logger.warning(f"关闭上下文 {context_id} 失败: {e}")
            self._active_contexts.clear()

            # 关闭浏览器
            if self._browser:
                try:
                    await self._browser.close()
                except Exception as e:
                    logger.warning(f"关闭浏览器失败: {e}")
                self._browser = None

            # 停止Playwright
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.warning(f"停止Playwright失败: {e}")
                self._playwright = None

            logger.info("Playwright资源清理完成")

    @property
    def active_context_count(self) -> int:
        """获取活跃上下文数量"""
        return len(self._active_contexts)


# 全局单例
_playwright_manager: Optional[PlaywrightManager] = None


def get_playwright_manager() -> PlaywrightManager:
    """获取Playwright管理器单例"""
    global _playwright_manager
    if _playwright_manager is None:
        _playwright_manager = PlaywrightManager()
    return _playwright_manager


async def cleanup_playwright():
    """清理Playwright资源"""
    global _playwright_manager
    if _playwright_manager:
        await _playwright_manager.cleanup()
        _playwright_manager = None
