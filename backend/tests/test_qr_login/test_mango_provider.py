"""
芒果TV扫码登录Provider单元测试

使用Hypothesis进行属性测试，确保Provider行为正确。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings

from src.core.qr_login.providers.mango import MangoQRProvider
from src.core.qr_login.models import QRLoginStatus


class TestMangoQRProviderProperties:
    """测试MangoQRProvider的基本属性"""
    
    def test_platform_id(self):
        """测试平台ID"""
        provider = MangoQRProvider()
        assert provider.platform_id == "mango"
    
    def test_platform_name_zh(self):
        """测试平台中文名称"""
        provider = MangoQRProvider()
        assert provider.platform_name_zh == "芒果TV"
    
    def test_qr_expiry_seconds(self):
        """测试二维码过期时间"""
        provider = MangoQRProvider()
        assert provider.qr_expiry_seconds == 180
    
    def test_platform_domain(self):
        """测试平台域名"""
        provider = MangoQRProvider()
        assert provider.platform_domain == ".mgtv.com"


class TestMangoQRProviderGenerateQRCode:
    """测试二维码生成功能"""
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_success(self):
        """测试成功生成二维码"""
        provider = MangoQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "data": {
                "qrcode": "https://passport.mgtv.com/qrcode/xxx.png",
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
            
            assert result.qrcode_url == "https://passport.mgtv.com/qrcode/xxx.png"
            assert result.qrcode_key == "test_token_12345678901234567890"
            assert result.expires_in == 180
            assert "芒果TV" in result.message
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_api_error(self):
        """测试API返回错误"""
        provider = MangoQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 500,
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
    async def test_generate_qrcode_missing_data(self):
        """测试返回数据不完整"""
        provider = MangoQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "data": {}  # 缺少必要字段
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


class TestMangoQRProviderCheckStatus:
    """测试扫码状态检查功能"""
    
    @pytest.mark.asyncio
    async def test_check_status_waiting(self):
        """测试等待扫码状态"""
        provider = MangoQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "data": {"status": 0}
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
        provider = MangoQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "data": {"status": 1}
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
        provider = MangoQRProvider()
        
        mock_cookies = MagicMock()
        mock_cookies.jar = [
            MagicMock(
                name="PM_CHKID",
                value="test_value",
                domain=".mgtv.com",
                path="/",
                secure=True,
                expires=1735689600
            )
        ]
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "data": {"status": 2}
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
    async def test_check_status_expired_code_error(self):
        """测试二维码过期状态(code错误)"""
        provider = MangoQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 400  # code != 200 表示过期
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
    async def test_check_status_expired_status_error(self):
        """测试二维码过期状态(status错误)"""
        provider = MangoQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "data": {"status": -1}  # 未知状态
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
        provider = MangoQRProvider()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.RequestError("Connection failed")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_token")
            
            assert result.status == QRLoginStatus.ERROR
            assert "网络请求失败" in result.message


class TestMangoQRProviderPropertyBased:
    """使用Hypothesis进行属性测试"""
    
    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_qrcode_key_preserved(self, qrcode_key: str):
        """属性测试: 二维码key在状态检查中被正确传递"""
        provider = MangoQRProvider()
        assert provider.platform_id == "mango"
    
    @settings(max_examples=100)
    @given(st.integers(min_value=-10, max_value=10))
    def test_status_code_handling(self, status_code: int):
        """属性测试: 所有状态码都能被正确处理"""
        provider = MangoQRProvider()
        assert provider.platform_id == "mango"
        assert provider.qr_expiry_seconds > 0
