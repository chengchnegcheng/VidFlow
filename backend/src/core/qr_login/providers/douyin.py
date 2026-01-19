"""
抖音扫码登录Provider

实现抖音的扫码登录功能，使用Playwright模拟浏览器。
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


class DouyinQRProvider(PlatformQRProvider):
    """抖音扫码登录Provider
    
    使用Playwright模拟浏览器获取抖音登录二维码：
    - 访问抖音首页
    - 点击登录按钮
    - 获取二维码图片
    - 检测登录状态（通过页面变化）
    """
    
    LOGIN_URL = "https://www.douyin.com/"
    
    def __init__(self):
        self._context_id: Optional[str] = None
        self._page = None
        self._qrcode_key: Optional[str] = None
    
    @property
    def platform_id(self) -> str:
        return "douyin"
    
    @property
    def platform_name_zh(self) -> str:
        return "抖音"
    
    @property
    def qr_expiry_seconds(self) -> int:
        return 180  # 3分钟
    
    @property
    def platform_domain(self) -> str:
        return ".douyin.com"
    
    async def generate_qrcode(self) -> QRCodeResult:
        """通过Playwright获取抖音登录二维码
        
        Returns:
            QRCodeResult: 包含二维码图片（base64）和key
            
        Raises:
            Exception: 获取二维码失败
        """
        manager = get_playwright_manager()
        
        try:
            # 创建唯一的上下文ID
            self._context_id = f"douyin_{uuid.uuid4().hex[:8]}"
            self._qrcode_key = self._context_id
            
            # 创建浏览器上下文
            context = await manager.create_context(
                self._context_id,
                use_stealth=True
            )
            
            # 创建页面
            self._page = await context.new_page()
            
            # 访问抖音首页
            logger.info("正在访问抖音首页...")
            await self._page.goto(self.LOGIN_URL, wait_until='networkidle', timeout=30000)
            
            # 等待页面加载
            await asyncio.sleep(2)
            
            # 尝试点击登录按钮
            try:
                # 抖音的登录按钮可能有多种选择器
                login_selectors = [
                    'button:has-text("登录")',
                    '[data-e2e="user-login"]',
                    '.login-btn',
                    'text=登录',
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
                'img[src*="qrcode"]',
                '.qrcode-image',
                '[data-e2e="qrcode-image"]',
                'img.qrcode',
                'canvas',  # 有些二维码是canvas绘制的
            ]
            
            qr_src = None
            for selector in qrcode_selectors:
                try:
                    qr_element = await self._page.wait_for_selector(selector, timeout=5000)
                    if qr_element:
                        if selector == 'canvas':
                            # 如果是canvas，截图获取
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
                # 如果无法获取二维码，截取整个登录区域
                try:
                    login_modal = await self._page.query_selector('.login-modal, .login-container, [data-e2e="login-modal"]')
                    if login_modal:
                        screenshot = await login_modal.screenshot()
                        qr_src = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                        logger.info("使用登录区域截图作为二维码")
                except Exception as e:
                    logger.warning(f"截取登录区域失败: {e}")
            
            if not qr_src:
                # 最后尝试截取整个页面
                screenshot = await self._page.screenshot()
                qr_src = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                logger.warning("使用整页截图作为二维码")
            
            logger.info(f"抖音二维码生成成功, context_id={self._context_id}")
            
            return QRCodeResult(
                qrcode_url=qr_src,
                qrcode_key=self._qrcode_key,
                expires_in=self.qr_expiry_seconds,
                message=f"请使用 {self.platform_name_zh} APP 扫描二维码登录"
            )
            
        except Exception as e:
            logger.error(f"抖音获取二维码失败: {e}")
            await self.cleanup()
            raise Exception(f"获取二维码失败: {str(e)}")
    
    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        """检查抖音扫码登录状态
        
        通过检测页面变化来判断登录状态。
        
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
            # 检查是否已登录（通过检测用户头像或登录状态变化）
            login_success_selectors = [
                '.user-avatar',
                '[data-e2e="user-avatar"]',
                '.user-info',
                '[data-e2e="user-info"]',
            ]
            
            for selector in login_success_selectors:
                try:
                    element = await self._page.query_selector(selector)
                    if element:
                        # 登录成功，提取Cookie
                        manager = get_playwright_manager()
                        context = await manager.get_context(self._context_id)
                        if context:
                            cookies = await context.cookies()
                            netscape_cookies = self.convert_to_netscape(cookies)
                            
                            logger.info("抖音扫码登录成功")
                            await self.cleanup()
                            
                            return QRLoginResult(
                                status=QRLoginStatus.SUCCESS,
                                message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                                cookies=netscape_cookies
                            )
                except Exception:
                    continue
            
            # 检查是否已扫码（通过页面文本）
            page_content = await self._page.content()
            
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
            
            # 检查URL变化（登录成功后可能会跳转）
            current_url = self._page.url
            if "passport" not in current_url and "login" not in current_url:
                # 可能已经登录成功并跳转
                manager = get_playwright_manager()
                context = await manager.get_context(self._context_id)
                if context:
                    cookies = await context.cookies()
                    # 检查是否有关键Cookie
                    cookie_names = [c.get('name', '') for c in cookies]
                    if any(name in cookie_names for name in ['sessionid', 'passport_csrf_token', 'ttwid']):
                        netscape_cookies = self.convert_to_netscape(cookies)
                        logger.info("抖音扫码登录成功（通过Cookie检测）")
                        await self.cleanup()
                        return QRLoginResult(
                            status=QRLoginStatus.SUCCESS,
                            message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                            cookies=netscape_cookies
                        )
            
            return QRLoginResult(
                status=QRLoginStatus.WAITING,
                message="等待扫码..."
            )
            
        except Exception as e:
            logger.error(f"抖音检查状态异常: {e}")
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
            logger.info("抖音Provider资源清理完成")
