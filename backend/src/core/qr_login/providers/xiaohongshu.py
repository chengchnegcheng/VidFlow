"""
小红书扫码登录Provider

实现小红书的扫码登录功能，使用Playwright模拟浏览器。
需要stealth脚本防止检测，并添加webId cookie防止滑块验证。
"""

import logging
import uuid
import base64
import asyncio
from typing import Optional, Dict, Any

from ..base_provider import PlatformQRProvider
from ..models import QRCodeResult, QRLoginResult, QRLoginStatus
from ..playwright_manager import get_playwright_manager

logger = logging.getLogger(__name__)


class XiaohongshuQRProvider(PlatformQRProvider):
    """小红书扫码登录Provider

    使用Playwright模拟浏览器获取小红书登录二维码：
    - 添加webId cookie防止滑块验证
    - 使用stealth脚本防止检测
    - 访问小红书首页
    - 点击登录按钮
    - 获取二维码图片
    - 检测登录状态（通过web_session变化）
    """

    LOGIN_URL = "https://www.xiaohongshu.com/"

    def __init__(self):
        self._context_id: Optional[str] = None
        self._page = None
        self._qrcode_key: Optional[str] = None
        self._initial_web_session: Optional[str] = None

    @property
    def platform_id(self) -> str:
        return "xiaohongshu"

    @property
    def platform_name_zh(self) -> str:
        return "小红书"

    @property
    def qr_expiry_seconds(self) -> int:
        return 120  # 2分钟

    @property
    def platform_domain(self) -> str:
        return ".xiaohongshu.com"

    async def generate_qrcode(self) -> QRCodeResult:
        """通过Playwright获取小红书登录二维码

        Returns:
            QRCodeResult: 包含二维码图片（base64）和key

        Raises:
            Exception: 获取二维码失败
        """
        manager = get_playwright_manager()

        try:
            # 创建唯一的上下文ID
            self._context_id = f"xiaohongshu_{uuid.uuid4().hex[:8]}"
            self._qrcode_key = self._context_id

            # 生成webId防止滑块验证
            web_id = str(uuid.uuid4())

            # 创建浏览器上下文，添加webId cookie
            context = await manager.create_context(
                self._context_id,
                use_stealth=True,
                extra_cookies=[{
                    'name': 'webId',
                    'value': web_id,
                    'domain': '.xiaohongshu.com',
                    'path': '/'
                }]
            )

            # 创建页面
            self._page = await context.new_page()

            # 访问小红书首页
            logger.info("正在访问小红书首页...")
            await self._page.goto(self.LOGIN_URL, wait_until='networkidle', timeout=30000)

            # 等待页面加载
            await asyncio.sleep(2)

            # 记录初始web_session
            cookies = await context.cookies()
            for cookie in cookies:
                if cookie.get('name') == 'web_session':
                    self._initial_web_session = cookie.get('value', '')
                    break

            # 尝试点击登录按钮
            try:
                login_selectors = [
                    'button:has-text("登录")',
                    '.login-btn',
                    '[data-v-login]',
                    'text=登录',
                    '.login-container button',
                ]

                for selector in login_selectors:
                    try:
                        login_btn = await self._page.wait_for_selector(selector, timeout=5000)
                        if login_btn:
                            await login_btn.click()
                            logger.info(f"点击登录按钮成功: {selector}")
                            break
                    except Exception:
                        continue

            except Exception as e:
                logger.warning(f"点击登录按钮失败: {e}")

            # 等待二维码出现
            await asyncio.sleep(2)

            # 尝试获取二维码图片
            qrcode_selectors = [
                'img.qrcode-img',
                'img[src*="qrcode"]',
                '.qrcode img',
                '[data-v-qrcode] img',
                'canvas.qrcode',
            ]

            qr_src = None
            for selector in qrcode_selectors:
                try:
                    qr_element = await self._page.wait_for_selector(selector, timeout=5000)
                    if qr_element:
                        if 'canvas' in selector:
                            screenshot = await qr_element.screenshot()
                            qr_src = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                        else:
                            qr_src = await qr_element.get_attribute('src')

                        if qr_src:
                            logger.info(f"获取二维码成功: {selector}")
                            break
                except Exception:
                    continue

            if not qr_src:
                # 截取登录区域
                try:
                    login_modal = await self._page.query_selector('.login-modal, .login-container, .qrcode-container')
                    if login_modal:
                        screenshot = await login_modal.screenshot()
                        qr_src = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                        logger.info("使用登录区域截图作为二维码")
                except Exception as e:
                    logger.warning(f"截取登录区域失败: {e}")

            if not qr_src:
                screenshot = await self._page.screenshot()
                qr_src = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                logger.warning("使用整页截图作为二维码")

            logger.info(f"小红书二维码生成成功, context_id={self._context_id}")

            return QRCodeResult(
                qrcode_url=qr_src,
                qrcode_key=self._qrcode_key,
                expires_in=self.qr_expiry_seconds,
                message=f"请使用 {self.platform_name_zh} APP 扫描二维码登录"
            )

        except Exception as e:
            logger.error(f"小红书获取二维码失败: {e}")
            await self.cleanup()
            raise Exception(f"获取二维码失败: {str(e)}")

    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        """检查小红书扫码登录状态

        通过检测web_session cookie变化来判断登录状态。

        Args:
            qrcode_key: 二维码唯一标识（context_id）

        Returns:
            QRLoginResult: 登录状态结果
        """
        if not self._page or qrcode_key != self._qrcode_key:
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message="请先获取二维码"
            )

        try:
            manager = get_playwright_manager()
            context = await manager.get_context(self._context_id)

            if not context:
                return QRLoginResult(
                    status=QRLoginStatus.ERROR,
                    message="浏览器上下文已关闭"
                )

            # 获取当前Cookie
            cookies = await context.cookies()
            cookie_dict = {c.get('name', ''): c.get('value', '') for c in cookies}

            # 检查web_session是否变化（登录后session会变长）
            current_web_session = cookie_dict.get('web_session', '')

            if current_web_session and len(current_web_session) > 50:
                # web_session变长，可能已登录
                if self._initial_web_session != current_web_session:
                    netscape_cookies = self.convert_to_netscape(cookies)
                    logger.info("小红书扫码登录成功")
                    await self.cleanup()
                    return QRLoginResult(
                        status=QRLoginStatus.SUCCESS,
                        message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                        cookies=netscape_cookies
                    )

            # 检查页面内容
            page_content = await self._page.content()

            if "请通过验证" in page_content or "滑块" in page_content:
                return QRLoginResult(
                    status=QRLoginStatus.ERROR,
                    message="需要手动验证，请稍后重试"
                )

            if "扫码成功" in page_content or "已扫码" in page_content:
                return QRLoginResult(
                    status=QRLoginStatus.SCANNED,
                    message="已扫码，请在手机上确认登录"
                )

            if "二维码已过期" in page_content or "已失效" in page_content:
                await self.cleanup()
                return QRLoginResult(
                    status=QRLoginStatus.EXPIRED,
                    message="二维码已过期，请重新获取"
                )

            # 检查是否有用户信息（登录成功的标志）
            user_selectors = [
                '.user-avatar',
                '.user-info',
                '[data-v-user]',
            ]

            for selector in user_selectors:
                try:
                    element = await self._page.query_selector(selector)
                    if element:
                        netscape_cookies = self.convert_to_netscape(cookies)
                        logger.info("小红书扫码登录成功（通过用户元素检测）")
                        await self.cleanup()
                        return QRLoginResult(
                            status=QRLoginStatus.SUCCESS,
                            message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                            cookies=netscape_cookies
                        )
                except Exception:
                    continue

            return QRLoginResult(
                status=QRLoginStatus.WAITING,
                message="等待扫码..."
            )

        except Exception as e:
            logger.error(f"小红书检查状态异常: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"检查状态失败: {str(e)}"
            )

    async def cleanup(self):
        """清理Playwright资源"""
        if self._context_id:
            manager = get_playwright_manager()
            await manager.close_context(self._context_id)
            self._context_id = None
            self._page = None
            self._qrcode_key = None
            self._initial_web_session = None
            logger.info("小红书Provider资源清理完成")
