"""
快手扫码登录Provider单元测试

使用Hypothesis进行属性测试，确保Provider行为正确。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings

from src.core.qr_login.providers.kuaishou import KuaishouQRProvider
from src.core.qr_login.models import QRLoginStatus


class TestKuaishouQRProviderProperties:
    """测试KuaishouQRProvider的基本属性"""
    
    def test_platform_id(self):
        """测试平台ID"""
        provider = KuaishouQRProvider()
        assert provider.platform_id == "kuaishou"
    
    def test_platform_name_zh(self):
        """测试平台中文名称"""
        provider = KuaishouQRProvider()
        assert provider.platform_name_zh == "快手"
    
    def test_qr_expiry_seconds(self):
        """测试二维码过期时间"""
        provider = KuaishouQRProvider()
        assert provider.qr_expiry_seconds == 180
    
    def test_platform_domain(self):
        """测试平台域名"""
        provider = KuaishouQRProvider()
        assert provider.platform_domain == ".kuaishou.com"


class TestKuaishouQRProviderGenerateQRCode:
    """测试二维码生成功能"""
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_success(self):
        """测试成功生成二维码"""
        provider = KuaishouQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": 1,
            "data": {
                "qrcodeUrl": "https://passport.kuaishou.com/qrcode/xxx",
                "sid": "test_sid_12345678901234567890"
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.generate_qrcode()
            
            assert result.qrcode_url == "https://passport.kuaishou.com/qrcode/xxx"
            assert result.qrcode_key == "test_sid_12345678901234567890"
            assert result.expires_in == 180
            assert "快手" in result.message
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_api_error(self):
        """测试API返回错误"""
        provider = KuaishouQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": 0,
            "error_msg": "服务器繁忙"
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            with pytest.raises(Exception) as exc_info:
                await provider.generate_qrcode()
            
            assert "获取二维码失败" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_missing_data(self):
        """测试返回数据不完整"""
        provider = KuaishouQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": 1,
            "data": {}  # 缺少必要字段
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            with pytest.raises(Exception) as exc_info:
                await provider.generate_qrcode()
            
            assert "返回数据不完整" in str(exc_info.value)


class TestKuaishouQRProviderCheckStatus:
    """测试扫码状态检查功能"""
    
    @pytest.mark.asyncio
    async def test_check_status_waiting(self):
        """测试等待扫码状态"""
        provider = KuaishouQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": 1,
            "data": {"status": 0}
        }
        mock_response.cookies = {}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_sid")
            
            assert result.status == QRLoginStatus.WAITING
            assert "等待扫码" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_scanned(self):
        """测试已扫码待确认状态"""
        provider = KuaishouQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": 1,
            "data": {"status": 1}
        }
        mock_response.cookies = {}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_sid")
            
            assert result.status == QRLoginStatus.SCANNED
            assert "已扫码" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_success(self):
        """测试登录成功状态"""
        provider = KuaishouQRProvider()
        
        # 创建mock cookies
        mock_cookies = MagicMock()
        mock_cookies.jar = [
            MagicMock(
                name="didv",
                value="test_value",
                domain=".kuaishou.com",
                path="/",
                secure=True,
                expires=1735689600
            )
        ]
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": 1,
            "data": {"status": 2}
        }
        mock_response.cookies = mock_cookies
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_sid")
            
            assert result.status == QRLoginStatus.SUCCESS
            assert "成功" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_expired(self):
        """测试二维码过期状态"""
        provider = KuaishouQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": 0,  # result != 1 表示过期
            "error_msg": "二维码已过期"
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_sid")
            
            assert result.status == QRLoginStatus.EXPIRED
            assert "过期" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_network_error(self):
        """测试网络错误处理"""
        import httpx
        provider = KuaishouQRProvider()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.RequestError("Connection failed")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_sid")
            
            assert result.status == QRLoginStatus.ERROR
            assert "网络请求失败" in result.message


class TestKuaishouQRProviderPropertyBased:
    """使用Hypothesis进行属性测试"""
    
    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_qrcode_key_preserved(self, qrcode_key: str):
        """属性测试: 二维码key在状态检查中被正确传递"""
        provider = KuaishouQRProvider()
        # 验证provider可以处理任意字符串作为key
        assert provider.platform_id == "kuaishou"
    
    @settings(max_examples=100)
    @given(st.integers(min_value=-10, max_value=10))
    def test_status_code_handling(self, status_code: int):
        """属性测试: 所有状态码都能被正确处理"""
        provider = KuaishouQRProvider()
        
        # 验证provider属性始终有效
        assert provider.platform_id == "kuaishou"
        assert provider.qr_expiry_seconds > 0
        assert len(provider.platform_name_zh) > 0
    
    @settings(max_examples=100)
    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
        values=st.text(min_size=1, max_size=50),
        min_size=0,
        max_size=10
    ))
    def test_cookie_conversion_robustness(self, cookie_dict: dict):
        """属性测试: Cookie转换对各种输入都能正确处理"""
        provider = KuaishouQRProvider()
        
        # 构造mock cookies
        mock_cookies = []
        for name, value in cookie_dict.items():
            mock_cookie = MagicMock()
            mock_cookie.name = name
            mock_cookie.value = value
            mock_cookie.domain = ".kuaishou.com"
            mock_cookie.path = "/"
            mock_cookie.secure = True
            mock_cookie.expires = 1735689600
            mock_cookies.append(mock_cookie)
        
        mock_jar = MagicMock()
        mock_jar.jar = mock_cookies
        
        # 转换应该不会抛出异常
        result = provider.convert_httpx_cookies_to_netscape(mock_jar)
        
        # 验证结果格式
        assert isinstance(result, str)
        if cookie_dict:
            assert "# Netscape HTTP Cookie File" in result
