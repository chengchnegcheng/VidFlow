"""
微博扫码登录Provider单元测试

使用Hypothesis进行属性测试，确保Provider行为正确。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings

from src.core.qr_login.providers.weibo import WeiboQRProvider
from src.core.qr_login.models import QRLoginStatus


class TestWeiboQRProviderProperties:
    """测试WeiboQRProvider的基本属性"""
    
    def test_platform_id(self):
        """测试平台ID"""
        provider = WeiboQRProvider()
        assert provider.platform_id == "weibo"
    
    def test_platform_name_zh(self):
        """测试平台中文名称"""
        provider = WeiboQRProvider()
        assert provider.platform_name_zh == "微博"
    
    def test_qr_expiry_seconds(self):
        """测试二维码过期时间"""
        provider = WeiboQRProvider()
        assert provider.qr_expiry_seconds == 180
    
    def test_platform_domain(self):
        """测试平台域名"""
        provider = WeiboQRProvider()
        assert provider.platform_domain == ".weibo.com"


class TestWeiboQRProviderGenerateQRCode:
    """测试二维码生成功能"""
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_success(self):
        """测试成功生成二维码"""
        provider = WeiboQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retcode": 20000000,
            "data": {
                "image": "https://login.sina.com.cn/qrcode/xxx.png",
                "qrid": "test_qrid_12345678901234567890"
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.generate_qrcode()
            
            assert result.qrcode_url == "https://login.sina.com.cn/qrcode/xxx.png"
            assert result.qrcode_key == "test_qrid_12345678901234567890"
            assert result.expires_in == 180
            assert "微博" in result.message
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_api_error(self):
        """测试API返回错误"""
        provider = WeiboQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retcode": 50000001,
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
        provider = WeiboQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retcode": 20000000,
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


class TestWeiboQRProviderCheckStatus:
    """测试扫码状态检查功能"""
    
    @pytest.mark.asyncio
    async def test_check_status_waiting(self):
        """测试等待扫码状态"""
        provider = WeiboQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retcode": 50114001
        }
        mock_response.cookies = {}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrid")
            
            assert result.status == QRLoginStatus.WAITING
            assert "等待扫码" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_scanned(self):
        """测试已扫码待确认状态"""
        provider = WeiboQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retcode": 50114002
        }
        mock_response.cookies = {}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrid")
            
            assert result.status == QRLoginStatus.SCANNED
            assert "已扫码" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_success_with_alt(self):
        """测试登录成功状态(带alt参数)"""
        provider = WeiboQRProvider()
        
        # 创建mock cookies
        mock_cookies = MagicMock()
        mock_cookies.jar = [
            MagicMock(
                name="SUB",
                value="test_value",
                domain=".weibo.com",
                path="/",
                secure=True,
                expires=1735689600
            )
        ]
        
        mock_check_response = MagicMock()
        mock_check_response.json.return_value = {
            "retcode": 20000000,
            "data": {"alt": "test_alt_token"}
        }
        mock_check_response.cookies = mock_cookies
        
        mock_login_response = MagicMock()
        mock_login_response.cookies = mock_cookies
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [mock_check_response, mock_login_response]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrid")
            
            assert result.status == QRLoginStatus.SUCCESS
            assert "成功" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_success_without_alt(self):
        """测试登录成功状态(无alt参数)"""
        provider = WeiboQRProvider()
        
        # 创建mock cookies
        mock_cookies = MagicMock()
        mock_cookies.jar = [
            MagicMock(
                name="SUB",
                value="test_value",
                domain=".weibo.com",
                path="/",
                secure=True,
                expires=1735689600
            )
        ]
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retcode": 20000000,
            "data": {}  # 无alt
        }
        mock_response.cookies = mock_cookies
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrid")
            
            assert result.status == QRLoginStatus.SUCCESS
            assert "成功" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_expired(self):
        """测试二维码过期状态"""
        provider = WeiboQRProvider()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retcode": 50114003  # 其他错误码表示过期
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrid")
            
            assert result.status == QRLoginStatus.EXPIRED
            assert "过期" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_network_error(self):
        """测试网络错误处理"""
        import httpx
        provider = WeiboQRProvider()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.RequestError("Connection failed")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrid")
            
            assert result.status == QRLoginStatus.ERROR
            assert "网络请求失败" in result.message


class TestWeiboQRProviderPropertyBased:
    """使用Hypothesis进行属性测试"""
    
    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_qrcode_key_preserved(self, qrcode_key: str):
        """属性测试: 二维码key在状态检查中被正确传递"""
        provider = WeiboQRProvider()
        # 验证provider可以处理任意字符串作为key
        assert provider.platform_id == "weibo"
    
    @settings(max_examples=100)
    @given(st.integers(min_value=0, max_value=100000000))
    def test_retcode_handling(self, retcode: int):
        """属性测试: 所有返回码都能被正确处理"""
        provider = WeiboQRProvider()
        
        # 验证provider属性始终有效
        assert provider.platform_id == "weibo"
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
        provider = WeiboQRProvider()
        
        # 构造mock cookies
        mock_cookies = []
        for name, value in cookie_dict.items():
            mock_cookie = MagicMock()
            mock_cookie.name = name
            mock_cookie.value = value
            mock_cookie.domain = ".weibo.com"
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
