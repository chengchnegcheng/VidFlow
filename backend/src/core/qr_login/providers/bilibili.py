"""
哔哩哔哩扫码登录Provider

实现B站的扫码登录功能，使用标准API方式。
"""

import logging
import httpx
from typing import Dict, Any

from ..base_provider import PlatformQRProvider
from ..models import QRCodeResult, QRLoginResult, QRLoginStatus

logger = logging.getLogger(__name__)


class BilibiliQRProvider(PlatformQRProvider):
    """哔哩哔哩扫码登录Provider

    使用B站官方API实现扫码登录：
    - 二维码生成: GET /x/passport-login/web/qrcode/generate
    - 状态轮询: GET /x/passport-login/web/qrcode/poll
    """

    # API URLs
    QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

    @property
    def platform_id(self) -> str:
        return "bilibili"

    @property
    def platform_name_zh(self) -> str:
        return "哔哩哔哩"

    @property
    def qr_expiry_seconds(self) -> int:
        return 180  # 3分钟

    @property
    def platform_domain(self) -> str:
        return ".bilibili.com"

    async def generate_qrcode(self) -> QRCodeResult:
        """生成B站登录二维码

        Returns:
            QRCodeResult: 包含二维码URL和key

        Raises:
            Exception: API请求失败或返回错误
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://www.bilibili.com/'

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self.QR_GENERATE_URL,
                headers=headers
            )
            data = response.json()

            if data.get('code') != 0:
                error_msg = data.get('message', '未知错误')
                logger.error(f"B站获取二维码失败: {error_msg}")
                raise Exception(f"获取二维码失败: {error_msg}")

            qrcode_key = data['data']['qrcode_key']
            qrcode_url = data['data']['url']

            logger.info(f"B站二维码生成成功, key={qrcode_key[:20]}...")

            return QRCodeResult(
                qrcode_url=qrcode_url,
                qrcode_key=qrcode_key,
                expires_in=self.qr_expiry_seconds,
                message=f"请使用 {self.platform_name_zh} APP 扫描二维码登录"
            )

    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        """检查B站扫码登录状态

        Args:
            qrcode_key: 二维码唯一标识

        Returns:
            QRLoginResult: 登录状态结果
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://www.bilibili.com/'

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.QR_POLL_URL,
                    params={'qrcode_key': qrcode_key},
                    headers=headers
                )
                data = response.json()

                code = data.get('data', {}).get('code', -1)

                # B站状态码说明：
                # 0: 登录成功
                # 86038: 二维码已失效
                # 86090: 已扫码未确认
                # 86101: 未扫码

                if code == 0:
                    # 登录成功，提取Cookie
                    cookies = self.convert_httpx_cookies_to_netscape(response.cookies)
                    logger.info("B站扫码登录成功")
                    return QRLoginResult(
                        status=QRLoginStatus.SUCCESS,
                        message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                        cookies=cookies
                    )
                elif code == 86038:
                    return QRLoginResult(
                        status=QRLoginStatus.EXPIRED,
                        message="二维码已过期，请重新获取"
                    )
                elif code == 86090:
                    return QRLoginResult(
                        status=QRLoginStatus.SCANNED,
                        message="已扫码，请在手机上确认登录"
                    )
                elif code == 86101:
                    return QRLoginResult(
                        status=QRLoginStatus.WAITING,
                        message="等待扫码..."
                    )
                else:
                    logger.warning(f"B站未知状态码: {code}")
                    return QRLoginResult(
                        status=QRLoginStatus.ERROR,
                        message=f"未知状态: {data.get('data', {}).get('message', '未知错误')}"
                    )

        except httpx.RequestError as e:
            logger.error(f"B站检查状态网络错误: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"网络请求失败: {str(e)}"
            )
        except Exception as e:
            logger.error(f"B站检查状态异常: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"检查状态失败: {str(e)}"
            )
