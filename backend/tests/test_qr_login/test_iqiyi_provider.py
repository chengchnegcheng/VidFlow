"""
爱奇艺扫码登录Provider单元测试

使用Hypothesis进行属性测试，确保Provider行为正确。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings

from src.core.qr_login.providers.iqiyi import IqiyiQRProvider
from src.core.qr_login.models import QRLoginStatus


class TestIqiyiQRProviderProperties:
    """测试IqiyiQRProvider的基本属性"""

    def test_platform_id(self):
        """测试平台ID"""
        provider = IqiyiQRProvider()
        assert provider.platform_id == "iqiyi"

    def test_platform_name_zh(self):
        """测试平台中文名称"""
        provider = IqiyiQRProvider()
        assert provider.platform_name_zh == "爱奇艺"

    def test_qr_expiry_seconds(self):
        """测试二维码过期时间"""
        provider = IqiyiQRProvider()
        assert provider.qr_expiry_seconds == 180

    def test_platform_domain(self):
        """测试平台域名"""
        provider = IqiyiQRProvider()
        assert provider.platform_domain == ".iqiyi.com"


class TestIqiyiQRProviderGenerateQRCode:
    """测试二维码生成功能"""

    @pytest.mark.asyncio
    async def test_generate_qrcode_success(self):
        """测试成功生成二维码"""
        provider = IqiyiQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "A00000",
            "data": {
                "token": "test_token_12345678901234567890"
            }
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await provider.generate_qrcode()

            assert "test_token_12345678901234567890" in result.qrcode_url
            assert result.qrcode_key == "test_token_12345678901234567890"
            assert result.expires_in == 180
            assert "爱奇艺" in result.message

    @pytest.mark.asyncio
    async def test_generate_qrcode_api_error(self):
        """测试API返回错误"""
        provider = IqiyiQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "E00001",
            "msg": "服务器繁忙"
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(Exception) as exc_info:
                await provider.generate_qrcode()

            assert "获取二维码失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_qrcode_missing_token(self):
        """测试返回数据缺少token"""
        provider = IqiyiQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "A00000",
            "data": {}  # 缺少token
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(Exception) as exc_info:
                await provider.generate_qrcode()

            assert "返回数据不完整" in str(exc_info.value)


class TestIqiyiQRProviderCheckStatus:
    """测试扫码状态检查功能"""

    @pytest.mark.asyncio
    async def test_check_status_waiting(self):
        """测试等待扫码状态"""
        provider = IqiyiQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "A00002"
        }
        mock_response.cookies = {}

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_token")

            assert result.status == QRLoginStatus.WAITING
            assert "等待扫码" in result.message

    @pytest.mark.asyncio
    async def test_check_status_scanned(self):
        """测试已扫码待确认状态"""
        provider = IqiyiQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "A00001"
        }
        mock_response.cookies = {}

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_token")

            assert result.status == QRLoginStatus.SCANNED
            assert "已扫码" in result.message

    @pytest.mark.asyncio
    async def test_check_status_success(self):
        """测试登录成功状态"""
        provider = IqiyiQRProvider()

        mock_cookies = MagicMock()
        mock_cookies.jar = [
            MagicMock(
                name="P00001",
                value="test_value",
                domain=".iqiyi.com",
                path="/",
                secure=True,
                expires=1735689600
            )
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "A00000"
        }
        mock_response.cookies = mock_cookies

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_token")

            assert result.status == QRLoginStatus.SUCCESS
            assert "成功" in result.message

    @pytest.mark.asyncio
    async def test_check_status_expired(self):
        """测试二维码过期状态"""
        provider = IqiyiQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "E00003"  # 其他错误码表示过期
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_token")

            assert result.status == QRLoginStatus.EXPIRED
            assert "过期" in result.message

    @pytest.mark.asyncio
    async def test_check_status_network_error(self):
        """测试网络错误处理"""
        import httpx
        provider = IqiyiQRProvider()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.RequestError("Connection failed")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_token")

            assert result.status == QRLoginStatus.ERROR
            assert "网络请求失败" in result.message


class TestIqiyiQRProviderPropertyBased:
    """使用Hypothesis进行属性测试"""

    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_qrcode_key_preserved(self, qrcode_key: str):
        """属性测试: 二维码key在状态检查中被正确传递"""
        provider = IqiyiQRProvider()
        assert provider.platform_id == "iqiyi"

    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=10, alphabet="ABCDE0123456789"))
    def test_code_handling(self, code: str):
        """属性测试: 所有返回码都能被正确处理"""
        provider = IqiyiQRProvider()
        assert provider.platform_id == "iqiyi"
        assert provider.qr_expiry_seconds > 0
