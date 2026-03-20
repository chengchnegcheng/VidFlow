"""
芒果TV扫码登录Provider

实现芒果TV的扫码登录功能，使用标准API方式。
"""

import logging
import httpx
from typing import Dict, Any

from ..base_provider import PlatformQRProvider
from ..models import QRCodeResult, QRLoginResult, QRLoginStatus

logger = logging.getLogger(__name__)


class MangoQRProvider(PlatformQRProvider):
    """芒果TV扫码登录Provider

    使用芒果TV官方API实现扫码登录：
    - 二维码生成: GET /qrcode/getQRCode
    - 状态轮询: GET /qrcode/getStatus
    """

    # API URLs
    QR_GENERATE_URL = "https://passport.mgtv.com/qrcode/getQRCode"
    QR_POLL_URL = "https://passport.mgtv.com/qrcode/getStatus"

    @property
    def platform_id(self) -> str:
        return "mango"

    @property
    def platform_name_zh(self) -> str:
        return "芒果TV"

    @property
    def qr_expiry_seconds(self) -> int:
        return 180  # 3分钟

    @property
    def platform_domain(self) -> str:
        return ".mgtv.com"

    async def generate_qrcode(self) -> QRCodeResult:
        """生成芒果TV登录二维码

        Returns:
            QRCodeResult: 包含二维码URL和key

        Raises:
            Exception: API请求失败或返回错误
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://www.mgtv.com/'

        params = {
            "src": "mgtv",
            "type": "1"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self.QR_GENERATE_URL,
                params=params,
                headers=headers
            )
            data = response.json()

            # 芒果TV API返回格式: {"code": 200, "data": {"qrcode": "...", "token": "..."}}
            if data.get('code') != 200:
                error_msg = data.get('msg', '未知错误')
                logger.error(f"芒果TV获取二维码失败: {error_msg}")
                raise Exception(f"获取二维码失败: {error_msg}")

            qrcode_data = data.get('data', {})
            qrcode_url = qrcode_data.get('qrcode', '')
            token = qrcode_data.get('token', '')

            if not qrcode_url or not token:
                logger.error("芒果TV返回数据缺少必要字段")
                raise Exception("获取二维码失败: 返回数据不完整")

            logger.info(f"芒果TV二维码生成成功, token={token[:20]}...")

            return QRCodeResult(
                qrcode_url=qrcode_url,
                qrcode_key=token,
                expires_in=self.qr_expiry_seconds,
                message=f"请使用 {self.platform_name_zh} APP 扫描二维码登录"
            )

    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        """检查芒果TV扫码登录状态

        Args:
            qrcode_key: 二维码唯一标识(token)

        Returns:
            QRLoginResult: 登录状态结果
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://www.mgtv.com/'

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

                code = data.get('code', -1)
                status = data.get('data', {}).get('status', -1)

                # 芒果TV状态码说明：
                # code=200 且 status=2: 登录成功
                # code=200 且 status=1: 已扫码待确认
                # code=200 且 status=0: 等待扫码
                # 其他: 二维码过期或错误

                if code != 200:
                    return QRLoginResult(
                        status=QRLoginStatus.EXPIRED,
                        message="二维码已过期，请重新获取"
                    )

                if status == 2:
                    # 登录成功，提取Cookie
                    cookies = self.convert_httpx_cookies_to_netscape(response.cookies)
                    logger.info("芒果TV扫码登录成功")
                    return QRLoginResult(
                        status=QRLoginStatus.SUCCESS,
                        message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                        cookies=cookies
                    )
                elif status == 1:
                    return QRLoginResult(
                        status=QRLoginStatus.SCANNED,
                        message="已扫码，请在手机上确认登录"
                    )
                elif status == 0:
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
            logger.error(f"芒果TV检查状态网络错误: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"网络请求失败: {str(e)}"
            )
        except Exception as e:
            logger.error(f"芒果TV检查状态异常: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"检查状态失败: {str(e)}"
            )
