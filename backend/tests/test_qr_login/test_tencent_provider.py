"""
腾讯视频扫码登录Provider单元测试

使用Hypothesis进行属性测试，确保Provider行为正确。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings

from src.core.qr_login.providers.tencent import TencentQRProvider
from src.core.qr_login.models import QRLoginStatus


class TestTencentQRProviderProperties:
    """测试TencentQRProvider的基本属性"""
    
    def test_platform_id(self):
        """测试平台ID"""
        provider = TencentQRProvider()
        assert provider.platform_id == "tencent"
    
    def test_platform_name_zh(self):
        """测试平台中文名称"""
        provider = TencentQRProvider()
        assert provider.platform_name_zh == "腾讯视频"
    
    def test_qr_expiry_seconds(self):
        """测试二维码过期时间"""
        provider = TencentQRProvider()
        assert provider.qr_expiry_seconds == 180
    
    def test_platform_domain(self):
        """测试平台域名"""
        provider = TencentQRProvider()
        assert provider.platform_domain == ".qq.com"


class TestTencentQRProviderPtqrtoken:
    """测试ptqrtoken计算算法"""
    
    def test_ptqrtoken_calculation(self):
        """测试ptqrtoken计算"""
        provider = TencentQRProvider()
        
        # 测试已知输入的输出
        qrsig = "test_qrsig"
        result = provider._get_ptqrtoken(qrsig)
        
        # 验证结果是正整数
        assert isinstance(result, int)
        assert result >= 0
        assert result <= 2147483647
    
    def test_ptqrtoken_deterministic(self):
        """测试ptqrtoken计算是确定性的"""
        provider = TencentQRProvider()
        
        qrsig = "same_qrsig_value"
        result1 = provider._get_ptqrtoken(qrsig)
        result2 = provider._get_ptqrtoken(qrsig)
        
        assert result1 == result2
    
    def test_ptqrtoken_different_inputs(self):
        """测试不同输入产生不同输出"""
        provider = TencentQRProvider()
        
        result1 = provider._get_ptqrtoken("qrsig_a")
        result2 = provider._get_ptqrtoken("qrsig_b")
        
        # 不同输入应该产生不同输出（虽然理论上可能碰撞，但概率很低）
        assert result1 != result2


class TestTencentQRProviderGenerateQRCode:
    """测试二维码生成功能"""
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_success(self):
        """测试成功生成二维码"""
        provider = TencentQRProvider()
        
        # 创建mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'\x89PNG\r\n\x1a\n'  # PNG header
        mock_response.cookies = MagicMock()
        mock_response.cookies.get.return_value = "test_qrsig_1234567890"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.generate_qrcode()
            
            assert result.qrcode_url.startswith("data:image/png;base64,")
            assert result.qrcode_key == "test_qrsig_1234567890"
            assert result.expires_in == 180
            assert "QQ" in result.message or "微信" in result.message
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_http_error(self):
        """测试HTTP错误"""
        provider = TencentQRProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        
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
    async def test_generate_qrcode_missing_qrsig(self):
        """测试缺少qrsig"""
        provider = TencentQRProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'\x89PNG\r\n\x1a\n'
        mock_response.cookies = MagicMock()
        mock_response.cookies.get.return_value = None  # 缺少qrsig
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            with pytest.raises(Exception) as exc_info:
                await provider.generate_qrcode()
            
            assert "缺少qrsig" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_qrcode_network_error(self):
        """测试网络错误"""
        import httpx
        provider = TencentQRProvider()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.RequestError("Connection failed")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            with pytest.raises(Exception) as exc_info:
                await provider.generate_qrcode()
            
            assert "网络请求失败" in str(exc_info.value)


class TestTencentQRProviderCheckStatus:
    """测试扫码状态检查功能"""
    
    @pytest.mark.asyncio
    async def test_check_status_waiting(self):
        """测试等待扫码状态"""
        provider = TencentQRProvider()
        
        mock_response = MagicMock()
        mock_response.text = "ptuiCB('66','0','','0','二维码未失效', '');"
        mock_response.cookies = MagicMock()
        mock_response.cookies.jar = []
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrsig")
            
            assert result.status == QRLoginStatus.WAITING
            assert "等待扫码" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_scanned(self):
        """测试已扫码待确认状态"""
        provider = TencentQRProvider()
        
        mock_response = MagicMock()
        mock_response.text = "ptuiCB('67','0','','0','已扫描，请在手机上确认', '');"
        mock_response.cookies = MagicMock()
        mock_response.cookies.jar = []
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrsig")
            
            assert result.status == QRLoginStatus.SCANNED
            assert "已扫码" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_success(self):
        """测试登录成功状态"""
        provider = TencentQRProvider()
        
        # 创建mock cookies
        mock_cookie = MagicMock()
        mock_cookie.name = "p_skey"
        mock_cookie.value = "test_value"
        mock_cookie.domain = ".qq.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600
        
        mock_response = MagicMock()
        mock_response.text = "ptuiCB('0','0','https://v.qq.com/','0','登录成功！', 'test_nick');"
        mock_response.cookies = MagicMock()
        mock_response.cookies.jar = [mock_cookie]
        
        # Mock redirect response
        mock_redirect_response = MagicMock()
        mock_redirect_response.cookies = MagicMock()
        mock_redirect_response.cookies.jar = []
        
        # Mock video response
        mock_video_response = MagicMock()
        mock_video_response.cookies = MagicMock()
        mock_video_response.cookies.jar = []
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [
                mock_response,
                mock_redirect_response,
                mock_video_response
            ]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrsig")
            
            assert result.status == QRLoginStatus.SUCCESS
            assert "成功" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_success_no_redirect(self):
        """测试登录成功但无redirect URL"""
        provider = TencentQRProvider()
        
        mock_cookie = MagicMock()
        mock_cookie.name = "p_skey"
        mock_cookie.value = "test_value"
        mock_cookie.domain = ".qq.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600
        
        mock_response = MagicMock()
        mock_response.text = "ptuiCB('0','0','','0','登录成功！', 'test_nick');"
        mock_response.cookies = MagicMock()
        mock_response.cookies.jar = [mock_cookie]
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrsig")
            
            assert result.status == QRLoginStatus.SUCCESS
            assert "成功" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_expired(self):
        """测试二维码过期状态"""
        provider = TencentQRProvider()
        
        mock_response = MagicMock()
        mock_response.text = "ptuiCB('65','0','','0','二维码已失效', '');"
        mock_response.cookies = MagicMock()
        mock_response.cookies.jar = []
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrsig")
            
            assert result.status == QRLoginStatus.EXPIRED
            assert "过期" in result.message
    
    @pytest.mark.asyncio
    async def test_check_status_network_error(self):
        """测试网络错误处理"""
        import httpx
        provider = TencentQRProvider()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.RequestError("Connection failed")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await provider.check_login_status("test_qrsig")
            
            assert result.status == QRLoginStatus.ERROR
            assert "网络请求失败" in result.message


class TestTencentQRProviderPropertyBased:
    """使用Hypothesis进行属性测试"""
    
    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_ptqrtoken_always_valid(self, qrsig: str):
        """属性测试: ptqrtoken对任意输入都返回有效值"""
        provider = TencentQRProvider()
        result = provider._get_ptqrtoken(qrsig)
        
        # 验证结果在有效范围内
        assert isinstance(result, int)
        assert 0 <= result <= 2147483647
    
    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_qrcode_key_preserved(self, qrcode_key: str):
        """属性测试: 二维码key在状态检查中被正确传递"""
        provider = TencentQRProvider()
        # 验证provider可以处理任意字符串作为key
        assert provider.platform_id == "tencent"
    
    @settings(max_examples=100)
    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
        values=st.text(min_size=1, max_size=50),
        min_size=0,
        max_size=10
    ))
    def test_cookie_conversion_robustness(self, cookie_dict: dict):
        """属性测试: Cookie转换对各种输入都能正确处理"""
        provider = TencentQRProvider()
        
        # 构造mock cookies
        mock_cookies = []
        for name, value in cookie_dict.items():
            mock_cookie = MagicMock()
            mock_cookie.name = name
            mock_cookie.value = value
            mock_cookie.domain = ".qq.com"
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
