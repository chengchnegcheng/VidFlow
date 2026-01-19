"""
爱奇艺扫码登录Provider

实现爱奇艺的扫码登录功能，使用标准API方式。
"""

import logging
import uuid
import httpx
from typing import Dict, Any

from ..base_provider import PlatformQRProvider
from ..models import QRCodeResult, QRLoginResult, QRLoginStatus

logger = logging.getLogger(__name__)


class IqiyiQRProvider(PlatformQRProvider):
    """爱奇艺扫码登录Provider
    
    使用爱奇艺官方API实现扫码登录：
    - 二维码生成: GET /apis/qrcode/gen_login_token.action
    - 状态轮询: GET /apis/qrcode/is_token_login.action
    """
    
    # API URLs
    QR_GENERATE_URL = "https://passport.iqiyi.com/apis/qrcode/gen_login_token.action"
    QR_POLL_URL = "https://passport.iqiyi.com/apis/qrcode/is_token_login.action"
    QR_IMAGE_URL = "https://passport.iqiyi.com/apis/qrcode/gen_qrcode.action"
    
    @property
    def platform_id(self) -> str:
        return "iqiyi"
    
    @property
    def platform_name_zh(self) -> str:
        return "爱奇艺"
    
    @property
    def qr_expiry_seconds(self) -> int:
        return 180  # 3分钟
    
    @property
    def platform_domain(self) -> str:
        return ".iqiyi.com"
    
    async def generate_qrcode(self) -> QRCodeResult:
        """生成爱奇艺登录二维码
        
        Returns:
            QRCodeResult: 包含二维码URL和key
            
        Raises:
            Exception: API请求失败或返回错误
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://www.iqiyi.com/'
        
        local_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())
        
        params = {
            "local_id": local_id,
            "app_version": "1.0.0",
            "device_id": device_id,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self.QR_GENERATE_URL,
                params=params,
                headers=headers
            )
            data = response.json()
            
            # 爱奇艺API返回格式: {"code": "A00000", "data": {"token": "..."}}
            if data.get('code') != 'A00000':
                error_msg = data.get('msg', '未知错误')
                logger.error(f"爱奇艺获取二维码失败: {error_msg}")
                raise Exception(f"获取二维码失败: {error_msg}")
            
            token = data.get('data', {}).get('token', '')
            
            if not token:
                logger.error("爱奇艺返回数据缺少token")
                raise Exception("获取二维码失败: 返回数据不完整")
            
            # 构造二维码图片URL
            qrcode_url = f"{self.QR_IMAGE_URL}?token={token}"
            
            logger.info(f"爱奇艺二维码生成成功, token={token[:20]}...")
            
            return QRCodeResult(
                qrcode_url=qrcode_url,
                qrcode_key=token,
                expires_in=self.qr_expiry_seconds,
                message=f"请使用 {self.platform_name_zh} APP 扫描二维码登录"
            )
    
    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        """检查爱奇艺扫码登录状态
        
        Args:
            qrcode_key: 二维码唯一标识(token)
            
        Returns:
            QRLoginResult: 登录状态结果
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://www.iqiyi.com/'
        
        params = {
            "token": qrcode_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.QR_POLL_URL,
                    params=params,
                    headers=headers
                )
                data = response.json()
                
                code = data.get('code', '')
                
                # 爱奇艺状态码说明：
                # A00000: 登录成功
                # A00001: 已扫码待确认
                # A00002: 等待扫码
                # 其他: 二维码过期或错误
                
                if code == 'A00000':
                    # 登录成功，提取Cookie
                    cookies = self.convert_httpx_cookies_to_netscape(response.cookies)
                    logger.info("爱奇艺扫码登录成功")
                    return QRLoginResult(
                        status=QRLoginStatus.SUCCESS,
                        message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                        cookies=cookies
                    )
                elif code == 'A00001':
                    return QRLoginResult(
                        status=QRLoginStatus.SCANNED,
                        message="已扫码，请在手机上确认登录"
                    )
                elif code == 'A00002':
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
            logger.error(f"爱奇艺检查状态网络错误: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"网络请求失败: {str(e)}"
            )
        except Exception as e:
            logger.error(f"爱奇艺检查状态异常: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"检查状态失败: {str(e)}"
            )
