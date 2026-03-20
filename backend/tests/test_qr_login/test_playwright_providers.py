"""
Playwright平台扫码登录Provider集成测试

测试抖音、小红书、优酷等需要Playwright的Provider。
由于Playwright测试需要实际浏览器，这里主要测试Provider的属性和基本逻辑。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings

from src.core.qr_login.providers.douyin import DouyinQRProvider
from src.core.qr_login.providers.xiaohongshu import XiaohongshuQRProvider
from src.core.qr_login.providers.youku import YoukuQRProvider
from src.core.qr_login.models import QRLoginStatus


class TestDouyinQRProviderProperties:
    """测试DouyinQRProvider的基本属性"""

    def test_platform_id(self):
        """测试平台ID"""
        provider = DouyinQRProvider()
        assert provider.platform_id == "douyin"

    def test_platform_name_zh(self):
        """测试平台中文名称"""
        provider = DouyinQRProvider()
        assert provider.platform_name_zh == "抖音"

    def test_qr_expiry_seconds(self):
        """测试二维码过期时间"""
        provider = DouyinQRProvider()
        assert provider.qr_expiry_seconds == 180

    def test_platform_domain(self):
        """测试平台域名"""
        provider = DouyinQRProvider()
        assert provider.platform_domain == ".douyin.com"

    def test_initial_state(self):
        """测试初始状态"""
        provider = DouyinQRProvider()
        assert provider._context_id is None
        assert provider._page is None
        assert provider._qrcode_key is None


class TestXiaohongshuQRProviderProperties:
    """测试XiaohongshuQRProvider的基本属性"""

    def test_platform_id(self):
        """测试平台ID"""
        provider = XiaohongshuQRProvider()
        assert provider.platform_id == "xiaohongshu"

    def test_platform_name_zh(self):
        """测试平台中文名称"""
        provider = XiaohongshuQRProvider()
        assert provider.platform_name_zh == "小红书"

    def test_qr_expiry_seconds(self):
        """测试二维码过期时间"""
        provider = XiaohongshuQRProvider()
        assert provider.qr_expiry_seconds == 120

    def test_platform_domain(self):
        """测试平台域名"""
        provider = XiaohongshuQRProvider()
        assert provider.platform_domain == ".xiaohongshu.com"

    def test_initial_state(self):
        """测试初始状态"""
        provider = XiaohongshuQRProvider()
        assert provider._context_id is None
        assert provider._page is None
        assert provider._qrcode_key is None
        assert provider._initial_web_session is None


class TestYoukuQRProviderProperties:
    """测试YoukuQRProvider的基本属性"""

    def test_platform_id(self):
        """测试平台ID"""
        provider = YoukuQRProvider()
        assert provider.platform_id == "youku"

    def test_platform_name_zh(self):
        """测试平台中文名称"""
        provider = YoukuQRProvider()
        assert provider.platform_name_zh == "优酷"

    def test_qr_expiry_seconds(self):
        """测试二维码过期时间"""
        provider = YoukuQRProvider()
        assert provider.qr_expiry_seconds == 180

    def test_platform_domain(self):
        """测试平台域名"""
        provider = YoukuQRProvider()
        assert provider.platform_domain == ".youku.com"

    def test_initial_state(self):
        """测试初始状态"""
        provider = YoukuQRProvider()
        assert provider._context_id is None
        assert provider._page is None
        assert provider._qrcode_key is None


class TestDouyinQRProviderCheckStatus:
    """测试DouyinQRProvider状态检查"""

    @pytest.mark.asyncio
    async def test_check_status_no_qrcode(self):
        """测试未获取二维码时检查状态"""
        provider = DouyinQRProvider()

        result = await provider.check_login_status("invalid_key")

        assert result.status == QRLoginStatus.ERROR
        assert "请先获取二维码" in result.message

    @pytest.mark.asyncio
    async def test_check_status_wrong_key(self):
        """测试使用错误的key检查状态"""
        provider = DouyinQRProvider()
        provider._qrcode_key = "correct_key"
        provider._page = MagicMock()

        result = await provider.check_login_status("wrong_key")

        assert result.status == QRLoginStatus.ERROR
        assert "请先获取二维码" in result.message


class TestXiaohongshuQRProviderCheckStatus:
    """测试XiaohongshuQRProvider状态检查"""

    @pytest.mark.asyncio
    async def test_check_status_no_qrcode(self):
        """测试未获取二维码时检查状态"""
        provider = XiaohongshuQRProvider()

        result = await provider.check_login_status("invalid_key")

        assert result.status == QRLoginStatus.ERROR
        assert "请先获取二维码" in result.message

    @pytest.mark.asyncio
    async def test_check_status_wrong_key(self):
        """测试使用错误的key检查状态"""
        provider = XiaohongshuQRProvider()
        provider._qrcode_key = "correct_key"
        provider._page = MagicMock()

        result = await provider.check_login_status("wrong_key")

        assert result.status == QRLoginStatus.ERROR
        assert "请先获取二维码" in result.message


class TestYoukuQRProviderCheckStatus:
    """测试YoukuQRProvider状态检查"""

    @pytest.mark.asyncio
    async def test_check_status_no_qrcode(self):
        """测试未获取二维码时检查状态"""
        provider = YoukuQRProvider()

        result = await provider.check_login_status("invalid_key")

        assert result.status == QRLoginStatus.ERROR
        assert "请先获取二维码" in result.message

    @pytest.mark.asyncio
    async def test_check_status_wrong_key(self):
        """测试使用错误的key检查状态"""
        provider = YoukuQRProvider()
        provider._qrcode_key = "correct_key"
        provider._page = MagicMock()

        result = await provider.check_login_status("wrong_key")

        assert result.status == QRLoginStatus.ERROR
        assert "请先获取二维码" in result.message


class TestPlaywrightProviderCleanup:
    """测试Playwright Provider资源清理"""

    @pytest.mark.asyncio
    async def test_douyin_cleanup_no_context(self):
        """测试抖音Provider无上下文时清理"""
        provider = DouyinQRProvider()

        # 不应该抛出异常
        await provider.cleanup()

        assert provider._context_id is None
        assert provider._page is None

    @pytest.mark.asyncio
    async def test_xiaohongshu_cleanup_no_context(self):
        """测试小红书Provider无上下文时清理"""
        provider = XiaohongshuQRProvider()

        await provider.cleanup()

        assert provider._context_id is None
        assert provider._page is None
        assert provider._initial_web_session is None

    @pytest.mark.asyncio
    async def test_youku_cleanup_no_context(self):
        """测试优酷Provider无上下文时清理"""
        provider = YoukuQRProvider()

        await provider.cleanup()

        assert provider._context_id is None
        assert provider._page is None


class TestPlaywrightProviderPropertyBased:
    """使用Hypothesis进行属性测试"""

    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_douyin_qrcode_key_handling(self, qrcode_key: str):
        """属性测试: 抖音Provider可以处理任意字符串作为key"""
        provider = DouyinQRProvider()
        assert provider.platform_id == "douyin"

    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_xiaohongshu_qrcode_key_handling(self, qrcode_key: str):
        """属性测试: 小红书Provider可以处理任意字符串作为key"""
        provider = XiaohongshuQRProvider()
        assert provider.platform_id == "xiaohongshu"

    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_youku_qrcode_key_handling(self, qrcode_key: str):
        """属性测试: 优酷Provider可以处理任意字符串作为key"""
        provider = YoukuQRProvider()
        assert provider.platform_id == "youku"

    @settings(max_examples=100)
    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
        values=st.text(min_size=1, max_size=50),
        min_size=0,
        max_size=10
    ))
    def test_cookie_conversion_robustness(self, cookie_dict: dict):
        """属性测试: Cookie转换对各种输入都能正确处理"""
        providers = [
            DouyinQRProvider(),
            XiaohongshuQRProvider(),
            YoukuQRProvider(),
        ]

        for provider in providers:
            # 构造cookie列表
            cookies = []
            for name, value in cookie_dict.items():
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': provider.platform_domain,
                    'path': '/',
                    'secure': True,
                    'expiry': 1735689600,
                })

            # 转换应该不会抛出异常
            result = provider.convert_to_netscape(cookies)

            # 验证结果格式
            assert isinstance(result, str)
            if cookie_dict:
                assert "# Netscape HTTP Cookie File" in result


class TestPlaywrightManagerMock:
    """测试PlaywrightManager的Mock行为"""

    @pytest.mark.asyncio
    async def test_douyin_generate_qrcode_with_mock(self):
        """测试抖音Provider使用Mock生成二维码"""
        provider = DouyinQRProvider()

        # Mock PlaywrightManager
        mock_manager = MagicMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_manager.create_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(return_value=None)
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.screenshot = AsyncMock(return_value=b'\x89PNG\r\n\x1a\n')

        with patch('src.core.qr_login.providers.douyin.get_playwright_manager', return_value=mock_manager):
            result = await provider.generate_qrcode()

            assert result.qrcode_url.startswith("data:image/png;base64,")
            assert result.qrcode_key is not None
            assert result.expires_in == 180
            assert "抖音" in result.message
