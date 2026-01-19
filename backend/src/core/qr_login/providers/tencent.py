"""
腾讯视频扫码登录Provider

实现腾讯视频的扫码登录功能，使用QQ登录体系。
"""

import logging
import random
import time
import base64
import re
import httpx
from typing import Dict, Any, Optional

from ..base_provider import PlatformQRProvider
from ..models import QRCodeResult, QRLoginResult, QRLoginStatus

logger = logging.getLogger(__name__)


class TencentQRProvider(PlatformQRProvider):
    """腾讯视频扫码登录Provider（使用QQ登录）
    
    使用QQ登录API实现扫码登录：
    - 二维码生成: GET /ptqrshow
    - 状态轮询: GET /ptqrlogin
    """
    
    # QQ登录API URLs
    QR_GENERATE_URL = "https://ssl.ptlogin2.qq.com/ptqrshow"
    QR_POLL_URL = "https://ssl.ptlogin2.qq.com/ptqrlogin"
    
    # 腾讯视频相关配置
    APPID = "716027609"  # 腾讯视频appid
    DAID = "383"
    
    def __init__(self):
        self._qrsig: Optional[str] = None
    
    @property
    def platform_id(self) -> str:
        return "tencent"
    
    @property
    def platform_name_zh(self) -> str:
        return "腾讯视频"
    
    @property
    def qr_expiry_seconds(self) -> int:
        return 180  # 3分钟
    
    @property
    def platform_domain(self) -> str:
        return ".qq.com"
    
    def _get_ptqrtoken(self, qrsig: str) -> int:
        """计算ptqrtoken
        
        QQ登录使用的hash算法，用于验证请求合法性。
        
        Args:
            qrsig: 二维码签名
            
        Returns:
            计算后的ptqrtoken值
        """
        e = 0
        for c in qrsig:
            e += (e << 5) + ord(c)
        return 2147483647 & e
    
    async def generate_qrcode(self) -> QRCodeResult:
        """生成腾讯视频登录二维码
        
        Returns:
            QRCodeResult: 包含二维码图片（base64）和key
            
        Raises:
            Exception: API请求失败
        """
        params = {
            "appid": self.APPID,
            "e": "2",
            "l": "M",
            "s": "3",
            "d": "72",
            "v": "4",
            "t": str(random.random()),
            "daid": self.DAID,
            "pt_3rd_aid": "0"
        }
        
        headers = self.get_default_headers()
        headers['Referer'] = 'https://v.qq.com/'
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.QR_GENERATE_URL,
                    params=params,
                    headers=headers
                )
                
                # 检查响应
                if response.status_code != 200:
                    logger.error(f"腾讯视频获取二维码失败: HTTP {response.status_code}")
                    raise Exception(f"获取二维码失败: HTTP {response.status_code}")
                
                # 获取qrsig cookie
                qrsig = response.cookies.get("qrsig")
                if not qrsig:
                    logger.error("腾讯视频返回数据缺少qrsig")
                    raise Exception("获取二维码失败: 缺少qrsig")
                
                self._qrsig = qrsig
                
                # 将二维码图片转为base64
                qrcode_base64 = base64.b64encode(response.content).decode()
                qrcode_url = f"data:image/png;base64,{qrcode_base64}"
                
                logger.info(f"腾讯视频二维码生成成功, qrsig={qrsig[:20]}...")
                
                return QRCodeResult(
                    qrcode_url=qrcode_url,
                    qrcode_key=qrsig,
                    expires_in=self.qr_expiry_seconds,
                    message=f"请使用 QQ 或 微信 扫描二维码登录"
                )
                
        except httpx.RequestError as e:
            logger.error(f"腾讯视频获取二维码网络错误: {e}")
            raise Exception(f"网络请求失败: {str(e)}")
    
    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        """检查腾讯视频扫码登录状态
        
        Args:
            qrcode_key: 二维码签名(qrsig)
            
        Returns:
            QRLoginResult: 登录状态结果
        """
        ptqrtoken = self._get_ptqrtoken(qrcode_key)
        
        params = {
            "u1": "https://v.qq.com/",
            "ptqrtoken": str(ptqrtoken),
            "ptredirect": "0",
            "h": "1",
            "t": "1",
            "g": "1",
            "from_ui": "1",
            "ptlang": "2052",
            "action": f"0-0-{int(time.time() * 1000)}",
            "js_ver": "21122814",
            "js_type": "1",
            "pt_uistyle": "40",
            "aid": self.APPID,
            "daid": self.DAID,
            "pt_3rd_aid": "0"
        }
        
        headers = self.get_default_headers()
        headers['Referer'] = 'https://xui.ptlogin2.qq.com/'
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.QR_POLL_URL,
                    params=params,
                    cookies={"qrsig": qrcode_key},
                    headers=headers
                )
                
                text = response.text
                
                # 解析响应，格式类似: ptuiCB('0','0','url','0','登录成功！', 'nickname');
                if "登录成功" in text:
                    # 提取登录凭证URL
                    match = re.search(r"'(https?://[^']+)'", text)
                    if match:
                        redirect_url = match.group(1)
                        # 获取腾讯视频的Cookie
                        cookies = await self._get_video_cookies(client, redirect_url, response.cookies)
                        logger.info("腾讯视频扫码登录成功")
                        return QRLoginResult(
                            status=QRLoginStatus.SUCCESS,
                            message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                            cookies=cookies
                        )
                    else:
                        # 没有redirect URL，直接使用当前cookies
                        cookies = self.convert_httpx_cookies_to_netscape(response.cookies)
                        logger.info("腾讯视频扫码登录成功(无redirect)")
                        return QRLoginResult(
                            status=QRLoginStatus.SUCCESS,
                            message=f"{self.platform_name_zh} Cookie 获取成功并已保存",
                            cookies=cookies
                        )
                        
                elif "已扫描" in text or "已扫码" in text:
                    return QRLoginResult(
                        status=QRLoginStatus.SCANNED,
                        message="已扫码，请在手机上确认登录"
                    )
                elif "二维码未失效" in text:
                    return QRLoginResult(
                        status=QRLoginStatus.WAITING,
                        message="等待扫码..."
                    )
                elif "二维码已失效" in text or "二维码已过期" in text:
                    return QRLoginResult(
                        status=QRLoginStatus.EXPIRED,
                        message="二维码已过期，请重新获取"
                    )
                else:
                    # 检查错误码
                    match = re.search(r"ptuiCB\('(\d+)'", text)
                    if match:
                        code = match.group(1)
                        if code == "66":
                            return QRLoginResult(
                                status=QRLoginStatus.WAITING,
                                message="等待扫码..."
                            )
                        elif code == "67":
                            return QRLoginResult(
                                status=QRLoginStatus.SCANNED,
                                message="已扫码，请在手机上确认登录"
                            )
                        elif code == "65":
                            return QRLoginResult(
                                status=QRLoginStatus.EXPIRED,
                                message="二维码已过期，请重新获取"
                            )
                    
                    logger.warning(f"腾讯视频未知响应: {text[:200]}")
                    return QRLoginResult(
                        status=QRLoginStatus.WAITING,
                        message="等待扫码..."
                    )
                    
        except httpx.RequestError as e:
            logger.error(f"腾讯视频检查状态网络错误: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"网络请求失败: {str(e)}"
            )
        except Exception as e:
            logger.error(f"腾讯视频检查状态异常: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"检查状态失败: {str(e)}"
            )
    
    async def _get_video_cookies(
        self, 
        client: httpx.AsyncClient, 
        redirect_url: str,
        initial_cookies
    ) -> str:
        """获取腾讯视频的完整Cookie
        
        登录成功后需要访问redirect URL来获取v.qq.com的Cookie。
        
        Args:
            client: httpx客户端
            redirect_url: 登录成功后的重定向URL
            initial_cookies: 初始Cookie
            
        Returns:
            Netscape格式的Cookie字符串
        """
        all_cookies = []
        
        # 添加初始cookies
        for cookie in initial_cookies.jar:
            all_cookies.append({
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path,
                'secure': cookie.secure,
                'expiry': cookie.expires,
            })
        
        try:
            # 访问redirect URL获取更多Cookie
            headers = self.get_default_headers()
            response = await client.get(
                redirect_url,
                headers=headers,
                follow_redirects=True,
                cookies=initial_cookies
            )
            
            # 添加新获取的cookies
            for cookie in response.cookies.jar:
                all_cookies.append({
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'secure': cookie.secure,
                    'expiry': cookie.expires,
                })
            
            # 尝试访问v.qq.com获取视频站点的Cookie
            try:
                video_response = await client.get(
                    "https://v.qq.com/",
                    headers=headers,
                    follow_redirects=True,
                    cookies=response.cookies
                )
                
                for cookie in video_response.cookies.jar:
                    all_cookies.append({
                        'name': cookie.name,
                        'value': cookie.value,
                        'domain': cookie.domain,
                        'path': cookie.path,
                        'secure': cookie.secure,
                        'expiry': cookie.expires,
                    })
            except Exception as e:
                logger.warning(f"获取v.qq.com Cookie失败: {e}")
                
        except Exception as e:
            logger.warning(f"访问redirect URL失败: {e}")
        
        return self.convert_to_netscape(all_cookies)
