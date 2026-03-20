"""
平台注册表完整性属性测试

**Property 6: Platform Registry Completeness**
**Validates: Requirements 8.2**

测试注册表的完整性：
- 每个注册的平台都包含所有必需字段
- 注册和获取操作正确
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.core.qr_login.base_provider import PlatformQRProvider
from src.core.qr_login.models import QRCodeResult, QRLoginResult, QRLoginStatus
from src.core.qr_login.registry import PlatformQRRegistry, reset_qr_registry


# 创建测试用Provider工厂
def create_test_provider(platform_id: str, platform_name_zh: str, qr_expiry_seconds: int):
    """创建测试用Provider"""

    class DynamicTestProvider(PlatformQRProvider):
        @property
        def platform_id(self) -> str:
            return platform_id

        @property
        def platform_name_zh(self) -> str:
            return platform_name_zh

        @property
        def qr_expiry_seconds(self) -> int:
            return qr_expiry_seconds

        async def generate_qrcode(self) -> QRCodeResult:
            return QRCodeResult(
                qrcode_url="https://test.com/qr",
                qrcode_key="test_key",
                expires_in=qr_expiry_seconds,
                message=f"请使用 {platform_name_zh} APP 扫描二维码"
            )

        async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
            return QRLoginResult(
                status=QRLoginStatus.WAITING,
                message="等待扫码"
            )

    return DynamicTestProvider()


# ============ Hypothesis策略定义 ============

# 平台ID策略：小写字母和数字
platform_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='_'),
    min_size=1,
    max_size=20
).filter(lambda x: x[0].isalpha() if x else False)

# 平台中文名称策略
platform_name_zh_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lo', 'L')),
    min_size=1,
    max_size=10
)

# 过期时间策略：60-600秒
qr_expiry_strategy = st.integers(min_value=60, max_value=600)

# 平台配置策略
platform_config_strategy = st.fixed_dictionaries({
    'platform_id': platform_id_strategy,
    'platform_name_zh': platform_name_zh_strategy,
    'qr_expiry_seconds': qr_expiry_strategy,
})

# 多个平台配置策略（确保platform_id唯一）
def unique_platforms_strategy(min_size=1, max_size=10):
    """生成具有唯一platform_id的平台配置列表"""
    return st.lists(
        platform_config_strategy,
        min_size=min_size,
        max_size=max_size,
        unique_by=lambda x: x['platform_id']
    )


# ============ 属性测试 ============

class TestPlatformRegistryCompleteness:
    """平台注册表完整性属性测试类

    **Feature: multi-platform-qr-login, Property 6: Platform Registry Completeness**
    """

    def setup_method(self):
        """每个测试前重置注册表"""
        reset_qr_registry()

    @given(platforms=unique_platforms_strategy(min_size=1, max_size=5))
    @settings(max_examples=100, deadline=None)
    def test_registered_platforms_have_all_required_fields(self, platforms):
        """
        Property 6.1: 注册的平台包含所有必需字段

        *For any* platform registered in the QR login registry, the registry entry
        SHALL contain: Platform ID, Platform name in Chinese, QR code expiration time,
        Enabled/disabled status.

        **Validates: Requirements 8.2**
        """
        registry = PlatformQRRegistry()

        # 注册所有平台
        for config in platforms:
            provider = create_test_provider(
                config['platform_id'],
                config['platform_name_zh'],
                config['qr_expiry_seconds']
            )
            registry.register(provider)

        # 获取支持的平台列表
        supported = registry.get_supported_platforms()

        # 验证每个平台都有所有必需字段
        for platform in supported:
            assert 'platform_id' in platform, "Missing platform_id"
            assert 'platform_name_zh' in platform, "Missing platform_name_zh"
            assert 'qr_expiry_seconds' in platform, "Missing qr_expiry_seconds"
            assert 'enabled' in platform, "Missing enabled"

            # 验证字段类型
            assert isinstance(platform['platform_id'], str), "platform_id should be string"
            assert isinstance(platform['platform_name_zh'], str), "platform_name_zh should be string"
            assert isinstance(platform['qr_expiry_seconds'], int), "qr_expiry_seconds should be int"
            assert isinstance(platform['enabled'], bool), "enabled should be bool"

            # 验证字段非空
            assert platform['platform_id'], "platform_id should not be empty"
            assert platform['platform_name_zh'], "platform_name_zh should not be empty"
            assert platform['qr_expiry_seconds'] > 0, "qr_expiry_seconds should be positive"

    @given(platforms=unique_platforms_strategy(min_size=1, max_size=5))
    @settings(max_examples=100, deadline=None)
    def test_registered_platforms_count_matches(self, platforms):
        """
        Property 6.2: 注册的平台数量正确

        *For any* set of platforms registered, the registry SHALL return
        exactly the same number of platforms.

        **Validates: Requirements 8.2**
        """
        registry = PlatformQRRegistry()

        for config in platforms:
            provider = create_test_provider(
                config['platform_id'],
                config['platform_name_zh'],
                config['qr_expiry_seconds']
            )
            registry.register(provider)

        supported = registry.get_supported_platforms()
        assert len(supported) == len(platforms), \
            f"Expected {len(platforms)} platforms, got {len(supported)}"

    @given(platforms=unique_platforms_strategy(min_size=1, max_size=5))
    @settings(max_examples=100, deadline=None)
    def test_get_provider_returns_registered_provider(self, platforms):
        """
        Property 6.3: 获取Provider返回正确的实例

        *For any* registered and enabled platform, get_provider SHALL return
        the corresponding provider instance.

        **Validates: Requirements 8.2**
        """
        registry = PlatformQRRegistry()

        providers = {}
        for config in platforms:
            provider = create_test_provider(
                config['platform_id'],
                config['platform_name_zh'],
                config['qr_expiry_seconds']
            )
            registry.register(provider, enabled=True)
            providers[config['platform_id']] = provider

        # 验证每个平台都能获取到Provider
        for platform_id, expected_provider in providers.items():
            actual_provider = registry.get_provider(platform_id)
            assert actual_provider is not None, f"Provider for {platform_id} should not be None"
            assert actual_provider.platform_id == platform_id, \
                f"Provider platform_id mismatch: expected {platform_id}, got {actual_provider.platform_id}"

    @given(platforms=unique_platforms_strategy(min_size=1, max_size=5))
    @settings(max_examples=100, deadline=None)
    def test_disabled_platforms_not_returned_by_get_provider(self, platforms):
        """
        Property 6.4: 禁用的平台不会被get_provider返回

        *For any* disabled platform, get_provider SHALL return None.

        **Validates: Requirements 8.4**
        """
        registry = PlatformQRRegistry()

        for config in platforms:
            provider = create_test_provider(
                config['platform_id'],
                config['platform_name_zh'],
                config['qr_expiry_seconds']
            )
            registry.register(provider, enabled=False)

        # 验证禁用的平台返回None
        for config in platforms:
            provider = registry.get_provider(config['platform_id'])
            assert provider is None, \
                f"Disabled platform {config['platform_id']} should return None"

    @given(platforms=unique_platforms_strategy(min_size=1, max_size=5))
    @settings(max_examples=100, deadline=None)
    def test_enable_disable_toggle(self, platforms):
        """
        Property 6.5: 启用/禁用切换正确工作

        *For any* platform, toggling enabled status SHALL correctly update
        the platform's availability.

        **Validates: Requirements 8.4**
        """
        registry = PlatformQRRegistry()

        for config in platforms:
            provider = create_test_provider(
                config['platform_id'],
                config['platform_name_zh'],
                config['qr_expiry_seconds']
            )
            registry.register(provider, enabled=True)

        # 禁用所有平台
        for config in platforms:
            registry.set_enabled(config['platform_id'], False)
            assert not registry.is_enabled(config['platform_id']), \
                f"Platform {config['platform_id']} should be disabled"
            assert registry.get_provider(config['platform_id']) is None, \
                f"Disabled platform {config['platform_id']} should return None"

        # 重新启用所有平台
        for config in platforms:
            registry.set_enabled(config['platform_id'], True)
            assert registry.is_enabled(config['platform_id']), \
                f"Platform {config['platform_id']} should be enabled"
            assert registry.get_provider(config['platform_id']) is not None, \
                f"Enabled platform {config['platform_id']} should return provider"


# ============ 单元测试 ============

class TestPlatformRegistryUnit:
    """平台注册表单元测试"""

    def setup_method(self):
        """每个测试前重置注册表"""
        reset_qr_registry()

    def test_empty_registry(self):
        """测试空注册表"""
        registry = PlatformQRRegistry()

        assert registry.get_supported_platforms() == []
        assert registry.get_enabled_platforms() == []
        assert registry.get_provider("nonexistent") is None
        assert not registry.has_platform("nonexistent")

    def test_register_and_unregister(self):
        """测试注册和注销"""
        registry = PlatformQRRegistry()
        provider = create_test_provider("test", "测试", 180)

        # 注册
        registry.register(provider)
        assert registry.has_platform("test")
        assert registry.get_provider("test") is not None

        # 注销
        result = registry.unregister("test")
        assert result is True
        assert not registry.has_platform("test")
        assert registry.get_provider("test") is None

        # 注销不存在的平台
        result = registry.unregister("nonexistent")
        assert result is False

    def test_clear_registry(self):
        """测试清空注册表"""
        registry = PlatformQRRegistry()

        # 注册多个平台
        for i in range(3):
            provider = create_test_provider(f"test{i}", f"测试{i}", 180)
            registry.register(provider)

        assert len(registry.get_supported_platforms()) == 3

        # 清空
        registry.clear()
        assert len(registry.get_supported_platforms()) == 0

    def test_get_all_platform_ids(self):
        """测试获取所有平台ID"""
        registry = PlatformQRRegistry()

        platform_ids = ["bilibili", "douyin", "kuaishou"]
        for pid in platform_ids:
            provider = create_test_provider(pid, f"{pid}中文", 180)
            registry.register(provider)

        all_ids = registry.get_all_platform_ids()
        assert set(all_ids) == set(platform_ids)

    def test_get_enabled_platforms(self):
        """测试获取已启用的平台"""
        registry = PlatformQRRegistry()

        # 注册3个平台，2个启用，1个禁用
        provider1 = create_test_provider("p1", "平台1", 180)
        provider2 = create_test_provider("p2", "平台2", 180)
        provider3 = create_test_provider("p3", "平台3", 180)

        registry.register(provider1, enabled=True)
        registry.register(provider2, enabled=True)
        registry.register(provider3, enabled=False)

        enabled = registry.get_enabled_platforms()
        assert len(enabled) == 2

        enabled_ids = {p['platform_id'] for p in enabled}
        assert enabled_ids == {"p1", "p2"}
