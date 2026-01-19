"""
微博扫码登录Provider

实现微博的扫码登录功能，使用标准API方式。
"""

import logging
import httpx
from typing import Dict, Any, Optional

from ..base_provider import PlatformQRProvider
from ..models import QRCodeResult, QRLoginResult, QRLoginStatus

logger = logging.getLogger(__name__)


class WeiboQRProvider(PlatformQRProvider):
    """微博扫码登录Provider
    
    使用微博官方API实现扫码登录：
    - 二维码生成: GET /sso/qrcode/image
    - 状态轮询: GET /sso/qrcode/check
    """
    
    # API URLs
    QR_GENERATE_URL = "https://login.sina.com.cn/sso/qrcode/image"
    QR_POLL_URL = "https://login.sina.com.cn/sso/qrcode/check"
    SSO_LOGIN_URL = "https://login.sina.com.cn/sso/login.php"
    
    @property
    def platform_id(self) -> str:
        return "weibo"
    
    @property
    def platform_name_zh(self) -> str:
        return "微博"
    
    @property
    def qr_expiry_seconds(self) -> int:
        return 180  # 3分钟
    
    @property
    def platform_domain(self) -> str:
        return ".weibo.com"
    
    async def generate_qrcode(self) -> QRCodeResult:
        """生成微博登录二维码
        
        Returns:
            QRCodeResult: 包含二维码URL和key
            
        Raises:
            Exception: API请求失败或返回错误
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://weibo.com/'
        
        params = {
            "entry": "weibo",
            "size": "180",
            "callback": ""
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self.QR_GENERATE_URL,
                params=params,
                headers=headers
            )
            data = response.json()
            
            # 微博API返回格式: {"retcode": 20000000, "data": {"image": "...", "qrid": "..."}}
            if data.get('retcode') != 20000000:
                error_msg = data.get('msg', '未知错误')
                logger.error(f"微博获取二维码失败: {error_msg}")
                raise Exception(f"获取二维码失败: {error_msg}")
            
            qrcode_data = data.get('data', {})
            qrcode_image = qrcode_data.get('image', '')
            qrid = qrcode_data.get('qrid', '')
            
            if not qrcode_image or not qrid:
                logger.error("微博返回数据缺少必要字段")
                raise Exception("获取二维码失败: 返回数据不完整")
            
            logger.info(f"微博二维码生成成功, qrid={qrid[:20]}...")
            
            return QRCodeResult(
                qrcode_url=qrcode_image,
                qrcode_key=qrid,
                expires_in=self.qr_expiry_seconds,
                message=f"请使用 {self.platform_name_zh} APP 扫描二维码登录"
            )
    
    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        """检查微博扫码登录状态
        
        Args:
            qrcode_key: 二维码唯一标识(qrid)
            
        Returns:
            QRLoginResult: 登录状态结果
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://weibo.com/'
        
        params = {
            "entry": "weibo",
            "qrid": qrcode_key,
            "callback": ""
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.QR_POLL_URL,
                    params=params,
                    headers=headers
                )
                data = response.json()
                
                retcode = data.get('retcode')
                
                # 微博状态码说明：
                # 20000000: 登录成功
                # 50114002: 已扫码待确认
                # 50114001: 等待扫码
                # 其他: 二维码过期或错误
                
                if retcode == 20000000:
                    # 登录成功，需要额外请求获取完整Cookie
                    alt = data.get('data', {}).get('alt', '')
                    if alt:
                        cookies = await self._get_full_cookies(client, alt)
                        logger.info("微博扫码登录成功")
                        return QRLoginResult(
                            status=QRLoginStatus.SUCCESS,
                            message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                            cookies=cookies
                        )
                    else:
                        # 没有alt，直接使用响应中的cookies
                        cookies = self.convert_httpx_cookies_to_netscape(response.cookies)
                        logger.info("微博扫码登录成功(无alt)")
                        return QRLoginResult(
                            status=QRLoginStatus.SUCCESS,
                            message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                            cookies=cookies
                        )
                elif retcode == 50114002:
                    return QRLoginResult(
                        status=QRLoginStatus.SCANNED,
                        message="已扫码，请在手机上确认登录"
                    )
                elif retcode == 50114001:
                    return QRLoginResult(
                        status=QRLoginStatus.WAITING,
                        message="等待扫码..."
                    )
                else:
                    return QRLoginResult(
                        status=QRLoginStatus.EXPIRED,
                        message="二维码已过期，请重新获取"
                    )
                    
        except httpx.RequestError as e:
            logger.error(f"微博检查状态网络错误: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"网络请求失败: {str(e)}"
            )
        except Exception as e:
            logger.error(f"微博检查状态异常: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"检查状态失败: {str(e)}"
            )
    
    async def _get_full_cookies(self, client: httpx.AsyncClient, alt: str) -> str:
        """获取完整的微博Cookie
        
        微博登录成功后需要通过alt参数获取完整的Cookie
        
        Args:
            client: httpx客户端
            alt: 登录成功后返回的alt参数
            
        Returns:
            Netscape格式的Cookie字符串
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://weibo.com/'
        
        params = {
            "entry": "weibo",
            "returntype": "TEXT",
            "crossdomain": "1",
            "cdult": "3",
            "domain": "weibo.com",
            "alt": alt,
            "savestate": "30",
            "callback": ""
        }
        
        try:
            response = await client.get(
                self.SSO_LOGIN_URL,
                params=params,
                headers=headers,
                follow_redirects=True
            )
            
            # 合并所有cookies
            return self.convert_httpx_cookies_to_netscape(response.cookies)
            
        except Exception as e:
            logger.error(f"微博获取完整Cookie失败: {e}")
            raise
