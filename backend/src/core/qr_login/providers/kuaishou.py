"""
快手扫码登录Provider

实现快手的扫码登录功能，使用标准API方式。
"""

import logging
import httpx
from typing import Dict, Any

from ..base_provider import PlatformQRProvider
from ..models import QRCodeResult, QRLoginResult, QRLoginStatus

logger = logging.getLogger(__name__)


class KuaishouQRProvider(PlatformQRProvider):
    """快手扫码登录Provider

    使用快手官方API实现扫码登录：
    - 二维码生成: POST /pc/qrcode/create
    - 状态轮询: GET /pc/qrcode/scan/result
    """

    # API URLs
    QR_GENERATE_URL = "https://passport.kuaishou.com/pc/qrcode/create"
    QR_POLL_URL = "https://passport.kuaishou.com/pc/qrcode/scan/result"

    @property
    def platform_id(self) -> str:
        return "kuaishou"

    @property
    def platform_name_zh(self) -> str:
        return "快手"

    @property
    def qr_expiry_seconds(self) -> int:
        return 180  # 3分钟

    @property
    def platform_domain(self) -> str:
        return ".kuaishou.com"

    async def generate_qrcode(self) -> QRCodeResult:
        """生成快手登录二维码

        Returns:
            QRCodeResult: 包含二维码URL和key

        Raises:
            Exception: API请求失败或返回错误
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://www.kuaishou.com/'
        headers['Origin'] = 'https://www.kuaishou.com'

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.QR_GENERATE_URL,
                headers=headers,
                json={}
            )
            data = response.json()

            # 快手API返回格式: {"result": 1, "data": {"qrcodeUrl": "...", "sid": "..."}}
            if data.get('result') != 1:
                error_msg = data.get('error_msg', '未知错误')
                logger.error(f"快手获取二维码失败: {error_msg}")
                raise Exception(f"获取二维码失败: {error_msg}")

            qrcode_data = data.get('data', {})
            qrcode_url = qrcode_data.get('qrcodeUrl', '')
            sid = qrcode_data.get('sid', '')

            if not qrcode_url or not sid:
                logger.error("快手返回数据缺少必要字段")
                raise Exception("获取二维码失败: 返回数据不完整")

            logger.info(f"快手二维码生成成功, sid={sid[:20]}...")

            return QRCodeResult(
                qrcode_url=qrcode_url,
                qrcode_key=sid,
                expires_in=self.qr_expiry_seconds,
                message=f"请使用 {self.platform_name_zh} APP 扫描二维码登录"
            )

    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        """检查快手扫码登录状态

        Args:
            qrcode_key: 二维码唯一标识(sid)

        Returns:
            QRLoginResult: 登录状态结果
        """
        headers = self.get_default_headers()
        headers['Referer'] = 'https://www.kuaishou.com/'

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.QR_POLL_URL,
                    params={'sid': qrcode_key},
                    headers=headers
                )
                data = response.json()

                # 快手状态码说明：
                # result=1 且 data.status=2: 登录成功
                # result=1 且 data.status=1: 已扫码待确认
                # result=1 且 data.status=0: 等待扫码
                # result!=1: 二维码过期或错误

                if data.get('result') != 1:
                    return QRLoginResult(
                        status=QRLoginStatus.EXPIRED,
                        message="二维码已过期，请重新获取"
                    )

                status = data.get('data', {}).get('status', -1)

                if status == 2:
                    # 登录成功，提取Cookie
                    cookies = self.convert_httpx_cookies_to_netscape(response.cookies)
                    logger.info("快手扫码登录成功")
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
                    logger.warning(f"快手未知状态码: {status}")
                    return QRLoginResult(
                        status=QRLoginStatus.ERROR,
                        message=f"未知状态: {status}"
                    )

        except httpx.RequestError as e:
            logger.error(f"快手检查状态网络错误: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"网络请求失败: {str(e)}"
            )
        except Exception as e:
            logger.error(f"快手检查状态异常: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"检查状态失败: {str(e)}"
            )
