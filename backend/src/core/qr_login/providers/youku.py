"""
优酷扫码登录Provider

实现优酷的扫码登录功能，使用Playwright模拟浏览器。
优酷使用阿里系登录，需要处理iframe中的二维码。
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


class YoukuQRProvider(PlatformQRProvider):
    """优酷扫码登录Provider（使用阿里登录）
    
    使用Playwright模拟浏览器获取优酷登录二维码：
    - 访问优酷首页
    - 点击登录按钮
    - 处理阿里登录iframe
    - 切换到扫码登录
    - 获取二维码图片
    - 检测登录状态
    """
    
    LOGIN_URL = "https://www.youku.com/"
    
    def __init__(self):
        self._context_id: Optional[str] = None
        self._page = None
        self._qrcode_key: Optional[str] = None
    
    @property
    def platform_id(self) -> str:
        return "youku"
    
    @property
    def platform_name_zh(self) -> str:
        return "优酷"
    
    @property
    def qr_expiry_seconds(self) -> int:
        return 180  # 3分钟
    
    @property
    def platform_domain(self) -> str:
        return ".youku.com"
    
    async def generate_qrcode(self) -> QRCodeResult:
        """通过Playwright获取优酷登录二维码
        
        Returns:
            QRCodeResult: 包含二维码图片（base64）和key
            
        Raises:
            Exception: 获取二维码失败
        """
        manager = get_playwright_manager()
        
        try:
            # 创建唯一的上下文ID
            self._context_id = f"youku_{uuid.uuid4().hex[:8]}"
            self._qrcode_key = self._context_id
            
            # 创建浏览器上下文
            context = await manager.create_context(
                self._context_id,
                use_stealth=True
            )
            
            # 创建页面
            self._page = await context.new_page()
            
            # 访问优酷首页
            logger.info("正在访问优酷首页...")
            await self._page.goto(self.LOGIN_URL, wait_until='networkidle', timeout=30000)
            
            # 等待页面加载
            await asyncio.sleep(2)
            
            # 尝试点击登录按钮
            try:
                login_selectors = [
                    'a.login-btn',
                    '.login-btn',
                    'button:has-text("登录")',
                    'text=登录',
                    '[data-spm*="login"]',
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
            
            # 等待登录iframe加载
            await asyncio.sleep(3)
            
            # 尝试处理阿里登录iframe
            qr_src = None
            
            try:
                # 查找阿里登录iframe
                iframe_selectors = [
                    'iframe#alibaba-login-box',
                    'iframe[src*="login.taobao"]',
                    'iframe[src*="login.alibaba"]',
                    'iframe.login-iframe',
                ]
                
                for iframe_selector in iframe_selectors:
                    try:
                        iframe = await self._page.wait_for_selector(iframe_selector, timeout=5000)
                        if iframe:
                            frame = await iframe.content_frame()
                            if frame:
                                # 在iframe中切换到扫码登录
                                qr_tab_selectors = [
                                    'text=扫码登录',
                                    '.qrcode-login',
                                    '[data-status="qrcode"]',
                                ]
                                
                                for tab_selector in qr_tab_selectors:
                                    try:
                                        qr_tab = await frame.wait_for_selector(tab_selector, timeout=3000)
                                        if qr_tab:
                                            await qr_tab.click()
                                            await asyncio.sleep(1)
                                            break
                                    except Exception:
                                        continue
                                
                                # 获取二维码图片
                                qr_selectors = [
                                    'img.qrcode-img',
                                    'img[src*="qrcode"]',
                                    '.qrcode img',
                                    'canvas.qrcode',
                                ]
                                
                                for qr_selector in qr_selectors:
                                    try:
                                        qr_element = await frame.wait_for_selector(qr_selector, timeout=3000)
                                        if qr_element:
                                            if 'canvas' in qr_selector:
                                                screenshot = await qr_element.screenshot()
                                                qr_src = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                                            else:
                                                qr_src = await qr_element.get_attribute('src')
                                            
                                            if qr_src:
                                                logger.info(f"从iframe获取二维码成功: {qr_selector}")
                                                break
                                    except Exception:
                                        continue
                                
                                if qr_src:
                                    break
                    except Exception:
                        continue
                        
            except Exception as e:
                logger.warning(f"处理iframe失败: {e}")
            
            # 如果iframe方式失败，尝试直接在页面获取
            if not qr_src:
                qrcode_selectors = [
                    'img[src*="qrcode"]',
                    '.qrcode-image',
                    'img.qrcode',
                    'canvas',
                ]
                
                for selector in qrcode_selectors:
                    try:
                        qr_element = await self._page.wait_for_selector(selector, timeout=5000)
                        if qr_element:
                            if selector == 'canvas':
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
                    login_modal = await self._page.query_selector('.login-modal, .login-container, iframe')
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
            
            logger.info(f"优酷二维码生成成功, context_id={self._context_id}")
            
            return QRCodeResult(
                qrcode_url=qr_src,
                qrcode_key=self._qrcode_key,
                expires_in=self.qr_expiry_seconds,
                message=f"请使用 淘宝 或 支付宝 APP 扫描二维码登录"
            )
            
        except Exception as e:
            logger.error(f"优酷获取二维码失败: {e}")
            await self.cleanup()
            raise Exception(f"获取二维码失败: {str(e)}")
    
    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        """检查优酷扫码登录状态
        
        通过检测页面变化和Cookie来判断登录状态。
        
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
            
            # 检查是否有登录成功的Cookie
            login_cookies = ['cna', 'P_ck_ctl', 'yk_uid', '_m_h5_tk']
            has_login_cookie = any(
                name in cookie_dict and cookie_dict[name] 
                for name in login_cookies
            )
            
            # 检查页面内容
            page_content = await self._page.content()
            
            # 检查是否已登录（通过用户信息）
            user_selectors = [
                '.user-avatar',
                '.user-info',
                '.login-success',
                '[data-spm*="user"]',
            ]
            
            for selector in user_selectors:
                try:
                    element = await self._page.query_selector(selector)
                    if element:
                        netscape_cookies = self.convert_to_netscape(cookies)
                        logger.info("优酷扫码登录成功")
                        await self.cleanup()
                        return QRLoginResult(
                            status=QRLoginStatus.SUCCESS,
                            message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                            cookies=netscape_cookies
                        )
                except Exception:
                    continue
            
            # 检查iframe中的状态
            try:
                iframe_selectors = [
                    'iframe#alibaba-login-box',
                    'iframe[src*="login.taobao"]',
                ]
                
                for iframe_selector in iframe_selectors:
                    try:
                        iframe = await self._page.query_selector(iframe_selector)
                        if iframe:
                            frame = await iframe.content_frame()
                            if frame:
                                frame_content = await frame.content()
                                
                                if "扫码成功" in frame_content or "已扫码" in frame_content:
                                    return QRLoginResult(
                                        status=QRLoginStatus.SCANNED,
                                        message="已扫码，请在手机上确认登录"
                                    )
                                
                                if "二维码已过期" in frame_content or "已失效" in frame_content:
                                    await self.cleanup()
                                    return QRLoginResult(
                                        status=QRLoginStatus.EXPIRED,
                                        message="二维码已过期，请重新获取"
                                    )
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"检查iframe状态失败: {e}")
            
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
            
            # 检查URL变化
            current_url = self._page.url
            if "youku.com" in current_url and "login" not in current_url.lower():
                # 可能已经登录成功
                if has_login_cookie:
                    netscape_cookies = self.convert_to_netscape(cookies)
                    logger.info("优酷扫码登录成功（通过Cookie检测）")
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
            logger.error(f"优酷检查状态异常: {e}")
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
            logger.info("优酷Provider资源清理完成")
