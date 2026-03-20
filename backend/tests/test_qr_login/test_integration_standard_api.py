"""
标准API平台集成测试

测试所有标准API平台（Bilibili, Kuaishou, Weibo, iQiyi, MangoTV）的完整扫码登录流程。
使用Mock模拟外部API响应。
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from hypothesis import given, strategies as st, settings

from src.core.qr_login import (
    QRLoginStatus,
    QRCodeResult,
    QRLoginResult,
    PlatformQRRegistry,
    QRLoginService,
    BilibiliQRProvider,
    KuaishouQRProvider,
    WeiboQRProvider,
    IqiyiQRProvider,
    MangoQRProvider,
    register_default_providers,
    get_qr_registry,
)


class TestRegistryIntegration:
    """测试注册表集成"""

    def test_register_default_providers(self):
        """测试默认Provider注册"""
        # 创建新的注册表
        registry = PlatformQRRegistry()

        # 手动注册所有Provider
        registry.register(BilibiliQRProvider(), enabled=True)
        registry.register(KuaishouQRProvider(), enabled=True)
        registry.register(WeiboQRProvider(), enabled=True)
        registry.register(IqiyiQRProvider(), enabled=True)
        registry.register(MangoQRProvider(), enabled=True)

        # 验证所有平台都已注册
        platforms = registry.get_supported_platforms()
        platform_ids = [p['platform_id'] for p in platforms]

        assert 'bilibili' in platform_ids
        assert 'kuaishou' in platform_ids
        assert 'weibo' in platform_ids
        assert 'iqiyi' in platform_ids
        assert 'mango' in platform_ids
        assert len(platform_ids) == 5

    def test_all_providers_have_required_properties(self):
        """测试所有Provider都有必需的属性"""
        providers = [
            BilibiliQRProvider(),
            KuaishouQRProvider(),
            WeiboQRProvider(),
            IqiyiQRProvider(),
            MangoQRProvider(),
        ]

        for provider in providers:
            # 验证必需属性
            assert provider.platform_id, f"{provider.__class__.__name__} 缺少 platform_id"
            assert provider.platform_name_zh, f"{provider.__class__.__name__} 缺少 platform_name_zh"
            assert provider.qr_expiry_seconds > 0, f"{provider.__class__.__name__} qr_expiry_seconds 必须大于0"

            # 验证属性类型
            assert isinstance(provider.platform_id, str)
            assert isinstance(provider.platform_name_zh, str)
            assert isinstance(provider.qr_expiry_seconds, int)

    def test_platform_ids_are_unique(self):
        """测试平台ID唯一性"""
        providers = [
            BilibiliQRProvider(),
            KuaishouQRProvider(),
            WeiboQRProvider(),
            IqiyiQRProvider(),
            MangoQRProvider(),
        ]

        platform_ids = [p.platform_id for p in providers]
        assert len(platform_ids) == len(set(platform_ids)), "存在重复的platform_id"


class TestBilibiliIntegration:
    """B站完整流程集成测试"""

    @pytest.mark.asyncio
    async def test_full_login_flow_success(self):
        """测试完整的登录成功流程"""
        provider = BilibiliQRProvider()

        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "code": 0,
            "data": {
                "url": "https://qr.bilibili.com/test123",
                "qrcode_key": "test_key_123"
            }
        }
        generate_response.raise_for_status = MagicMock()

        # Mock检查状态 - 登录成功
        poll_response = MagicMock()
        poll_response.json.return_value = {
            "code": 0,
            "data": {
                "code": 0,
                "message": "登录成功",
                "refresh_token": "test_refresh_token"
            }
        }
        poll_response.raise_for_status = MagicMock()

        # 创建mock cookies
        mock_cookie = MagicMock()
        mock_cookie.name = "SESSDATA"
        mock_cookie.value = "test_sessdata"
        mock_cookie.domain = ".bilibili.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600

        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        poll_response.cookies = mock_cookies

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[generate_response, poll_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            # 生成二维码
            qr_result = await provider.generate_qrcode()
            assert qr_result.qrcode_url == "https://qr.bilibili.com/test123"
            assert qr_result.qrcode_key == "test_key_123"

            # 检查状态
            login_result = await provider.check_login_status("test_key_123")
            assert login_result.status == QRLoginStatus.SUCCESS
            assert login_result.cookies is not None
            assert "SESSDATA" in login_result.cookies

    @pytest.mark.asyncio
    async def test_status_transitions(self):
        """测试状态转换流程: waiting -> scanned -> success"""
        provider = BilibiliQRProvider()

        # 状态序列
        status_responses = [
            {"code": 0, "data": {"code": 86101, "message": "等待扫码"}},  # waiting
            {"code": 0, "data": {"code": 86090, "message": "已扫码"}},    # scanned
        ]

        responses = []
        for resp_data in status_responses:
            mock_resp = MagicMock()
            mock_resp.json.return_value = resp_data
            mock_resp.raise_for_status = MagicMock()
            responses.append(mock_resp)

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=responses)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            # 第一次检查 - waiting
            result1 = await provider.check_login_status("test_key")
            assert result1.status == QRLoginStatus.WAITING

            # 第二次检查 - scanned
            result2 = await provider.check_login_status("test_key")
            assert result2.status == QRLoginStatus.SCANNED


class TestKuaishouIntegration:
    """快手完整流程集成测试"""

    @pytest.mark.asyncio
    async def test_full_login_flow_success(self):
        """测试完整的登录成功流程"""
        provider = KuaishouQRProvider()

        # Mock生成二维码 - 快手API格式: {"result": 1, "data": {"qrcodeUrl": "...", "sid": "..."}}
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "result": 1,
            "data": {
                "qrcodeUrl": "https://passport.kuaishou.com/qrcode/test123",
                "sid": "test_sid_123"
            }
        }
        generate_response.raise_for_status = MagicMock()

        # Mock检查状态 - 登录成功: {"result": 1, "data": {"status": 2}}
        poll_response = MagicMock()
        poll_response.json.return_value = {
            "result": 1,
            "data": {
                "status": 2
            }
        }
        poll_response.raise_for_status = MagicMock()

        # 创建mock cookies
        mock_cookie = MagicMock()
        mock_cookie.name = "passToken"
        mock_cookie.value = "test_pass_token"
        mock_cookie.domain = ".kuaishou.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600

        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        poll_response.cookies = mock_cookies

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=generate_response)
            mock_instance.get = AsyncMock(return_value=poll_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            # 生成二维码
            qr_result = await provider.generate_qrcode()
            assert "kuaishou" in qr_result.qrcode_url.lower() or qr_result.qrcode_url.startswith("https://")
            assert qr_result.qrcode_key == "test_sid_123"

            # 检查状态
            login_result = await provider.check_login_status("test_sid_123")
            assert login_result.status == QRLoginStatus.SUCCESS
            assert login_result.cookies is not None


class TestWeiboIntegration:
    """微博完整流程集成测试"""

    @pytest.mark.asyncio
    async def test_full_login_flow_with_alt(self):
        """测试完整的登录成功流程（带alt token）"""
        provider = WeiboQRProvider()

        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "retcode": 20000000,
            "data": {
                "image": "https://login.sina.com.cn/qrcode/test123.png",
                "qrid": "test_qrid_123"
            }
        }
        generate_response.raise_for_status = MagicMock()

        # Mock检查状态 - 登录成功（带alt）
        poll_response = MagicMock()
        poll_response.json.return_value = {
            "retcode": 20000000,
            "data": {
                "alt": "test_alt_token_123"
            }
        }
        poll_response.raise_for_status = MagicMock()

        # Mock获取完整Cookie
        alt_response = MagicMock()
        alt_response.raise_for_status = MagicMock()

        mock_cookie = MagicMock()
        mock_cookie.name = "SUB"
        mock_cookie.value = "test_sub_value"
        mock_cookie.domain = ".weibo.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600

        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        alt_response.cookies = mock_cookies

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[generate_response, poll_response, alt_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            # 生成二维码
            qr_result = await provider.generate_qrcode()
            assert qr_result.qrcode_key == "test_qrid_123"

            # 检查状态
            login_result = await provider.check_login_status("test_qrid_123")
            assert login_result.status == QRLoginStatus.SUCCESS
            assert login_result.cookies is not None


class TestIqiyiIntegration:
    """爱奇艺完整流程集成测试"""

    @pytest.mark.asyncio
    async def test_full_login_flow_success(self):
        """测试完整的登录成功流程"""
        provider = IqiyiQRProvider()

        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "code": "A00000",
            "data": {
                "token": "test_token_123"
            }
        }
        generate_response.raise_for_status = MagicMock()

        # Mock检查状态 - 登录成功
        poll_response = MagicMock()
        poll_response.json.return_value = {
            "code": "A00000",
            "data": {
                "status": 2
            }
        }
        poll_response.raise_for_status = MagicMock()

        # 创建mock cookies
        mock_cookie = MagicMock()
        mock_cookie.name = "P00001"
        mock_cookie.value = "test_p00001_value"
        mock_cookie.domain = ".iqiyi.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600

        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        poll_response.cookies = mock_cookies

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[generate_response, poll_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            # 生成二维码
            qr_result = await provider.generate_qrcode()
            assert qr_result.qrcode_key == "test_token_123"

            # 检查状态
            login_result = await provider.check_login_status("test_token_123")
            assert login_result.status == QRLoginStatus.SUCCESS
            assert login_result.cookies is not None


class TestMangoIntegration:
    """芒果TV完整流程集成测试"""

    @pytest.mark.asyncio
    async def test_full_login_flow_success(self):
        """测试完整的登录成功流程"""
        provider = MangoQRProvider()

        # Mock生成二维码 - 芒果TV API格式: {"code": 200, "data": {"qrcode": "...", "token": "..."}}
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "code": 200,
            "data": {
                "qrcode": "https://passport.mgtv.com/qrcode/test123.png",
                "token": "test_token_123"
            }
        }
        generate_response.raise_for_status = MagicMock()

        # Mock检查状态 - 登录成功: {"code": 200, "data": {"status": 2}}
        poll_response = MagicMock()
        poll_response.json.return_value = {
            "code": 200,
            "data": {
                "status": 2
            }
        }
        poll_response.raise_for_status = MagicMock()

        # 创建mock cookies
        mock_cookie = MagicMock()
        mock_cookie.name = "PM_CHKID"
        mock_cookie.value = "test_pm_chkid"
        mock_cookie.domain = ".mgtv.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600

        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        poll_response.cookies = mock_cookies

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[generate_response, poll_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            # 生成二维码
            qr_result = await provider.generate_qrcode()
            assert qr_result.qrcode_key == "test_token_123"

            # 检查状态
            login_result = await provider.check_login_status("test_token_123")
            assert login_result.status == QRLoginStatus.SUCCESS
            assert login_result.cookies is not None



class TestServiceIntegration:
    """QRLoginService集成测试"""

    @pytest.mark.asyncio
    async def test_service_with_all_providers(self):
        """测试服务与所有Provider的集成"""
        registry = PlatformQRRegistry()

        # 注册所有Provider
        registry.register(BilibiliQRProvider(), enabled=True)
        registry.register(KuaishouQRProvider(), enabled=True)
        registry.register(WeiboQRProvider(), enabled=True)
        registry.register(IqiyiQRProvider(), enabled=True)
        registry.register(MangoQRProvider(), enabled=True)

        # 创建服务
        service = QRLoginService(registry)

        # 验证所有平台都可以获取Provider
        for platform_id in ['bilibili', 'kuaishou', 'weibo', 'iqiyi', 'mango']:
            provider = registry.get_provider(platform_id)
            assert provider is not None, f"无法获取 {platform_id} Provider"

    @pytest.mark.asyncio
    async def test_service_qrcode_caching(self):
        """测试服务的二维码缓存功能"""
        registry = PlatformQRRegistry()
        registry.register(BilibiliQRProvider(), enabled=True)
        service = QRLoginService(registry)

        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "code": 0,
            "data": {
                "url": "https://qr.bilibili.com/test123",
                "qrcode_key": "test_key_123"
            }
        }
        generate_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=generate_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            # 获取二维码
            qr_result = await service.get_qrcode('bilibili')
            assert qr_result.qrcode_key == "test_key_123"

            # 验证缓存
            assert 'bilibili' in service._qrcode_cache
            assert service._qrcode_cache['bilibili']['key'] == "test_key_123"

    @pytest.mark.asyncio
    async def test_service_check_status_without_qrcode(self):
        """测试未获取二维码时检查状态"""
        registry = PlatformQRRegistry()
        registry.register(BilibiliQRProvider(), enabled=True)
        service = QRLoginService(registry)

        # 直接检查状态（未获取二维码）
        result = await service.check_status('bilibili')
        assert result.status == QRLoginStatus.ERROR
        assert "请先获取二维码" in result.message

    @pytest.mark.asyncio
    async def test_service_unsupported_platform(self):
        """测试不支持的平台"""
        registry = PlatformQRRegistry()
        service = QRLoginService(registry)

        # 尝试获取不支持的平台
        with pytest.raises(ValueError) as exc_info:
            await service.get_qrcode('unsupported_platform')
        assert "不支持扫码登录" in str(exc_info.value)


class TestCrossProviderConsistency:
    """跨Provider一致性测试"""

    def test_all_providers_return_correct_result_types(self):
        """测试所有Provider返回正确的结果类型"""
        providers = [
            BilibiliQRProvider(),
            KuaishouQRProvider(),
            WeiboQRProvider(),
            IqiyiQRProvider(),
            MangoQRProvider(),
        ]

        for provider in providers:
            # 验证方法签名
            assert hasattr(provider, 'generate_qrcode')
            assert hasattr(provider, 'check_login_status')
            assert hasattr(provider, 'convert_to_netscape')

    def test_all_providers_have_chinese_messages(self):
        """测试所有Provider都有中文提示消息"""
        providers = [
            BilibiliQRProvider(),
            KuaishouQRProvider(),
            WeiboQRProvider(),
            IqiyiQRProvider(),
            MangoQRProvider(),
        ]

        for provider in providers:
            # 验证平台名称是中文
            assert any('\u4e00' <= char <= '\u9fff' for char in provider.platform_name_zh), \
                f"{provider.platform_id} 的 platform_name_zh 不包含中文"

    def test_cookie_conversion_consistency(self):
        """测试Cookie转换的一致性"""
        providers = [
            BilibiliQRProvider(),
            KuaishouQRProvider(),
            WeiboQRProvider(),
            IqiyiQRProvider(),
            MangoQRProvider(),
        ]

        test_cookies = [
            {
                'name': 'test_cookie',
                'value': 'test_value',
                'domain': '.example.com',
                'path': '/',
                'secure': True,
                'expiry': 1735689600
            }
        ]

        for provider in providers:
            result = provider.convert_to_netscape(test_cookies)

            # 验证Netscape格式
            assert "# Netscape HTTP Cookie File" in result
            assert "test_cookie" in result
            assert "test_value" in result
            assert ".example.com" in result


class TestPropertyBasedIntegration:
    """属性测试 - 集成测试"""

    @settings(max_examples=100)
    @given(st.sampled_from(['bilibili', 'kuaishou', 'weibo', 'iqiyi', 'mango']))
    def test_registry_get_provider_consistency(self, platform_id):
        """Property: 注册表获取Provider的一致性"""
        registry = PlatformQRRegistry()

        # 注册所有Provider
        registry.register(BilibiliQRProvider(), enabled=True)
        registry.register(KuaishouQRProvider(), enabled=True)
        registry.register(WeiboQRProvider(), enabled=True)
        registry.register(IqiyiQRProvider(), enabled=True)
        registry.register(MangoQRProvider(), enabled=True)

        # 获取Provider
        provider = registry.get_provider(platform_id)

        # 验证
        assert provider is not None
        assert provider.platform_id == platform_id

    @settings(max_examples=100)
    @given(
        st.lists(
            st.fixed_dictionaries({
                'name': st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
                'value': st.text(min_size=0, max_size=200),
                'domain': st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
                'path': st.just('/'),
                'secure': st.booleans(),
                'expiry': st.integers(min_value=0, max_value=2147483647)
            }),
            min_size=1,
            max_size=10
        )
    )
    def test_all_providers_cookie_conversion_preserves_data(self, cookies):
        """Property: 所有Provider的Cookie转换保留数据"""
        providers = [
            BilibiliQRProvider(),
            KuaishouQRProvider(),
            WeiboQRProvider(),
            IqiyiQRProvider(),
            MangoQRProvider(),
        ]

        for provider in providers:
            result = provider.convert_to_netscape(cookies)

            # 验证所有Cookie都被转换
            for cookie in cookies:
                assert cookie['name'] in result
                assert cookie['domain'] in result

    @settings(max_examples=100)
    @given(st.sampled_from([
        QRLoginStatus.LOADING,
        QRLoginStatus.WAITING,
        QRLoginStatus.SCANNED,
        QRLoginStatus.SUCCESS,
        QRLoginStatus.EXPIRED,
        QRLoginStatus.ERROR
    ]))
    def test_qr_login_result_status_values(self, status):
        """Property: QRLoginResult状态值有效性"""
        result = QRLoginResult(
            status=status,
            message="测试消息"
        )

        assert result.status == status
        assert result.status.value in ['loading', 'waiting', 'scanned', 'success', 'expired', 'error']


class TestErrorHandlingIntegration:
    """错误处理集成测试"""

    @pytest.mark.asyncio
    async def test_network_error_handling_bilibili(self):
        """测试B站网络错误处理"""
        provider = BilibiliQRProvider()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_key")
            assert result.status == QRLoginStatus.ERROR
            assert "网络" in result.message or "失败" in result.message

    @pytest.mark.asyncio
    async def test_network_error_handling_kuaishou(self):
        """测试快手网络错误处理"""
        provider = KuaishouQRProvider()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_key")
            assert result.status == QRLoginStatus.ERROR

    @pytest.mark.asyncio
    async def test_network_error_handling_weibo(self):
        """测试微博网络错误处理"""
        provider = WeiboQRProvider()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_key")
            assert result.status == QRLoginStatus.ERROR

    @pytest.mark.asyncio
    async def test_network_error_handling_iqiyi(self):
        """测试爱奇艺网络错误处理"""
        provider = IqiyiQRProvider()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_key")
            assert result.status == QRLoginStatus.ERROR

    @pytest.mark.asyncio
    async def test_network_error_handling_mango(self):
        """测试芒果TV网络错误处理"""
        provider = MangoQRProvider()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("test_key")
            assert result.status == QRLoginStatus.ERROR


class TestQRCodeExpirationIntegration:
    """二维码过期集成测试"""

    @pytest.mark.asyncio
    async def test_bilibili_expiration(self):
        """测试B站二维码过期"""
        provider = BilibiliQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "code": 86038,
                "message": "二维码已过期"
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("expired_key")
            assert result.status == QRLoginStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_kuaishou_expiration(self):
        """测试快手二维码过期"""
        provider = KuaishouQRProvider()

        # 快手过期状态: result != 1
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": 0,  # result != 1 表示过期
            "error_msg": "二维码已过期"
        }
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("expired_key")
            assert result.status == QRLoginStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_weibo_expiration(self):
        """测试微博二维码过期"""
        provider = WeiboQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retcode": 50114003  # 过期状态
        }
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("expired_key")
            assert result.status == QRLoginStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_iqiyi_expiration(self):
        """测试爱奇艺二维码过期"""
        provider = IqiyiQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "A00003"  # 过期状态
        }
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("expired_key")
            assert result.status == QRLoginStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_mango_expiration(self):
        """测试芒果TV二维码过期"""
        provider = MangoQRProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "200",
            "data": {
                "status": 3  # 过期状态
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await provider.check_login_status("expired_key")
            assert result.status == QRLoginStatus.EXPIRED
