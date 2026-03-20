"""
BilibiliQRProvider 单元测试

测试B站扫码登录Provider的功能。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.core.qr_login.providers.bilibili import BilibiliQRProvider
from src.core.qr_login.models import QRLoginStatus


class TestBilibiliQRProviderProperties:
    """测试BilibiliQRProvider的属性"""

    def test_platform_id(self):
        """测试平台ID"""
        provider = BilibiliQRProvider()
        assert provider.platform_id == "bilibili"

    def test_platform_name_zh(self):
        """测试平台中文名称"""
        provider = BilibiliQRProvider()
        assert provider.platform_name_zh == "哔哩哔哩"

    def test_qr_expiry_seconds(self):
        """测试二维码过期时间"""
        provider = BilibiliQRProvider()
        assert provider.qr_expiry_seconds == 180

    def test_platform_domain(self):
        """测试平台域名"""
        provider = BilibiliQRProvider()
        assert provider.platform_domain == ".bilibili.com"


class TestBilibiliQRProviderGenerateQRCode:
    """测试BilibiliQRProvider的二维码生成"""

    @pytest.mark.asyncio
    async def test_generate_qrcode_success(self):
        """测试成功生成二维码"""
        provider = BilibiliQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'code': 0,
            'data': {
                'qrcode_key': 'test_qrcode_key_12345',
                'url': 'https://passport.bilibili.com/qrcode/h5/login?oauthKey=test'
            }
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await provider.generate_qrcode()

            assert result.qrcode_key == 'test_qrcode_key_12345'
            assert result.qrcode_url == 'https://passport.bilibili.com/qrcode/h5/login?oauthKey=test'
            assert result.expires_in == 180
            assert '哔哩哔哩' in result.message

    @pytest.mark.asyncio
    async def test_generate_qrcode_api_error(self):
        """测试API返回错误"""
        provider = BilibiliQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'code': -1,
            'message': '系统繁忙'
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            with pytest.raises(Exception) as exc_info:
                await provider.generate_qrcode()

            assert '获取二维码失败' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_qrcode_network_error(self):
        """测试网络错误"""
        provider = BilibiliQRProvider()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )

            with pytest.raises(httpx.RequestError):
                await provider.generate_qrcode()


class TestBilibiliQRProviderCheckStatus:
    """测试BilibiliQRProvider的状态检查"""

    @pytest.mark.asyncio
    async def test_check_status_waiting(self):
        """测试等待扫码状态"""
        provider = BilibiliQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'code': 0,
            'data': {
                'code': 86101,
                'message': '未扫码'
            }
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await provider.check_login_status('test_key')

            assert result.status == QRLoginStatus.WAITING
            assert '等待扫码' in result.message

    @pytest.mark.asyncio
    async def test_check_status_scanned(self):
        """测试已扫码待确认状态"""
        provider = BilibiliQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'code': 0,
            'data': {
                'code': 86090,
                'message': '已扫码未确认'
            }
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await provider.check_login_status('test_key')

            assert result.status == QRLoginStatus.SCANNED
            assert '确认' in result.message

    @pytest.mark.asyncio
    async def test_check_status_expired(self):
        """测试二维码过期状态"""
        provider = BilibiliQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'code': 0,
            'data': {
                'code': 86038,
                'message': '二维码已失效'
            }
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await provider.check_login_status('test_key')

            assert result.status == QRLoginStatus.EXPIRED
            assert '过期' in result.message

    @pytest.mark.asyncio
    async def test_check_status_success(self):
        """测试登录成功状态"""
        provider = BilibiliQRProvider()

        # 创建模拟的cookies
        mock_cookie = MagicMock()
        mock_cookie.name = 'SESSDATA'
        mock_cookie.value = 'test_session_value'
        mock_cookie.domain = '.bilibili.com'
        mock_cookie.path = '/'
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600

        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'code': 0,
            'data': {
                'code': 0,
                'message': '登录成功'
            }
        }
        mock_response.cookies = mock_cookies

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await provider.check_login_status('test_key')

            assert result.status == QRLoginStatus.SUCCESS
            assert result.cookies is not None
            assert 'SESSDATA' in result.cookies
            assert 'test_session_value' in result.cookies

    @pytest.mark.asyncio
    async def test_check_status_network_error(self):
        """测试网络错误处理"""
        provider = BilibiliQRProvider()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )

            result = await provider.check_login_status('test_key')

            assert result.status == QRLoginStatus.ERROR
            assert '网络' in result.message


class TestBilibiliQRProviderIntegration:
    """BilibiliQRProvider集成测试（需要网络）"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要真实网络连接，仅手动测试")
    async def test_real_qrcode_generation(self):
        """测试真实的二维码生成（手动测试用）"""
        provider = BilibiliQRProvider()
        result = await provider.generate_qrcode()

        assert result.qrcode_key
        assert result.qrcode_url
        assert result.expires_in == 180
        print(f"QR Code URL: {result.qrcode_url}")
        print(f"QR Code Key: {result.qrcode_key}")
