"""
Cookie格式转换属性测试

**Property 1: Cookie Format Conversion Correctness**
**Validates: Requirements 1.6, 7.1, 7.2, 7.5**

测试Cookie转换为Netscape格式的正确性：
- 包含所有7个必需字段
- 保留原始Cookie值
- 保留过期时间
"""

import time
import pytest
from hypothesis import given, strategies as st, settings, assume

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.core.qr_login.base_provider import PlatformQRProvider
from src.core.qr_login.models import QRCodeResult, QRLoginResult, QRLoginStatus


# 创建一个具体的Provider实现用于测试
class TestProvider(PlatformQRProvider):
    """测试用Provider实现"""

    @property
    def platform_id(self) -> str:
        return "test"

    @property
    def platform_name_zh(self) -> str:
        return "测试平台"

    @property
    def qr_expiry_seconds(self) -> int:
        return 180

    async def generate_qrcode(self) -> QRCodeResult:
        return QRCodeResult(
            qrcode_url="https://test.com/qr",
            qrcode_key="test_key",
            expires_in=180,
            message="测试消息"
        )

    async def check_login_status(self, qrcode_key: str) -> QRLoginResult:
        return QRLoginResult(
            status=QRLoginStatus.WAITING,
            message="等待扫码"
        )


# ============ Hypothesis策略定义 ============

# Cookie名称策略：非空字符串，不包含特殊字符
cookie_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip() != '')

# Cookie值策略：可以包含大多数字符，但不包含制表符和换行符
cookie_value_strategy = st.text(
    alphabet=st.characters(blacklist_characters='\t\n\r'),
    min_size=0,
    max_size=200
)

# 域名策略
domain_strategy = st.one_of(
    st.just('.bilibili.com'),
    st.just('.douyin.com'),
    st.just('.kuaishou.com'),
    st.just('.xiaohongshu.com'),
    st.just('.weibo.com'),
    st.just('www.example.com'),
    st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='.-'),
        min_size=3,
        max_size=30
    ).map(lambda x: f".{x}.com" if not x.startswith('.') else x)
)

# 路径策略
path_strategy = st.one_of(
    st.just('/'),
    st.just('/api'),
    st.just('/api/v1'),
    st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='/-_'),
        min_size=1,
        max_size=50
    ).map(lambda x: f"/{x}" if not x.startswith('/') else x)
)

# 过期时间策略：当前时间到未来一年
expiry_strategy = st.one_of(
    st.just(0),  # 会话Cookie
    st.integers(min_value=int(time.time()), max_value=int(time.time()) + 365 * 24 * 3600)
)

# 单个Cookie策略
cookie_strategy = st.fixed_dictionaries({
    'name': cookie_name_strategy,
    'value': cookie_value_strategy,
    'domain': domain_strategy,
    'path': path_strategy,
    'secure': st.booleans(),
    'expiry': expiry_strategy,
})

# Cookie列表策略
cookies_list_strategy = st.lists(cookie_strategy, min_size=1, max_size=20)


# ============ 属性测试 ============

class TestCookieFormatConversion:
    """Cookie格式转换属性测试类

    **Feature: multi-platform-qr-login, Property 1: Cookie Format Conversion Correctness**
    """

    @given(cookies=cookies_list_strategy)
    @settings(max_examples=100, deadline=None)
    def test_netscape_format_has_seven_fields(self, cookies):
        """
        Property 1.1: Netscape格式包含所有7个必需字段

        *For any* set of cookies, converting them to Netscape format SHALL produce
        lines with exactly 7 tab-separated fields for each cookie.

        **Validates: Requirements 7.1, 7.2**
        """
        provider = TestProvider()
        result = provider.convert_to_netscape(cookies)

        lines = result.split('\n')

        # 跳过注释行和空行
        data_lines = [line for line in lines if line and not line.startswith('#')]

        for line in data_lines:
            fields = line.split('\t')
            assert len(fields) == 7, f"Expected 7 fields, got {len(fields)}: {line}"

            # 验证字段顺序: domain, flag, path, secure, expiration, name, value
            domain, flag, path, secure, expiration, name, value = fields

            # domain不为空
            assert domain, "domain should not be empty"

            # flag是TRUE或FALSE
            assert flag in ('TRUE', 'FALSE'), f"flag should be TRUE or FALSE, got {flag}"

            # path不为空
            assert path, "path should not be empty"

            # secure是TRUE或FALSE
            assert secure in ('TRUE', 'FALSE'), f"secure should be TRUE or FALSE, got {secure}"

            # expiration是数字
            assert expiration.isdigit(), f"expiration should be numeric, got {expiration}"

            # name不为空
            assert name, "name should not be empty"

    @given(cookies=cookies_list_strategy)
    @settings(max_examples=100, deadline=None)
    def test_cookie_values_preserved(self, cookies):
        """
        Property 1.2: Cookie值被正确保留

        *For any* set of cookies, the converted Netscape format SHALL preserve
        the original cookie name and value without modification.

        **Validates: Requirements 7.1**
        """
        # 过滤掉重复name的cookie，只保留第一个（模拟实际行为）
        seen_names = set()
        unique_cookies = []
        for c in cookies:
            name = c.get('name', '')
            if name and name not in seen_names:
                seen_names.add(name)
                unique_cookies.append(c)

        provider = TestProvider()
        result = provider.convert_to_netscape(unique_cookies)

        lines = result.split('\n')
        data_lines = [line for line in lines if line and not line.startswith('#')]

        # 构建原始Cookie的name->value映射
        original_cookies = {c['name']: c['value'] for c in unique_cookies if c.get('name')}

        # 验证转换后的Cookie
        for line in data_lines:
            fields = line.split('\t')
            if len(fields) >= 7:
                name = fields[5]
                value = fields[6]

                # 验证name和value被保留
                if name in original_cookies:
                    assert value == original_cookies[name], \
                        f"Cookie value mismatch for {name}: expected {original_cookies[name]}, got {value}"

    @given(cookies=cookies_list_strategy)
    @settings(max_examples=100, deadline=None)
    def test_expiry_times_preserved(self, cookies):
        """
        Property 1.3: Cookie过期时间被正确保留

        *For any* set of cookies with non-zero expiry times, the converted
        Netscape format SHALL preserve the original expiration timestamps.

        **Validates: Requirements 7.5**
        """
        # 过滤掉重复name的cookie，只保留第一个
        seen_names = set()
        unique_cookies = []
        for c in cookies:
            name = c.get('name', '')
            if name and name not in seen_names:
                seen_names.add(name)
                unique_cookies.append(c)

        provider = TestProvider()
        result = provider.convert_to_netscape(unique_cookies)

        lines = result.split('\n')
        data_lines = [line for line in lines if line and not line.startswith('#')]

        # 构建原始Cookie的name->expiry映射（只包含非零过期时间）
        original_expiry = {
            c['name']: c.get('expiry', 0)
            for c in unique_cookies
            if c.get('name') and c.get('expiry', 0) > 0
        }

        for line in data_lines:
            fields = line.split('\t')
            if len(fields) >= 7:
                name = fields[5]
                expiration = int(fields[4])

                # 如果原始Cookie有非零过期时间，验证它被保留
                if name in original_expiry:
                    assert expiration == original_expiry[name], \
                        f"Expiry mismatch for {name}: expected {original_expiry[name]}, got {expiration}"

    @given(cookies=cookies_list_strategy)
    @settings(max_examples=100, deadline=None)
    def test_session_cookies_get_default_expiry(self, cookies):
        """
        Property 1.4: 会话Cookie获得默认过期时间

        *For any* session cookie (expiry=0), the converted Netscape format
        SHALL assign a default expiry time (approximately 1 year from now).

        **Validates: Requirements 7.5**
        """
        # 创建只包含会话Cookie的列表
        session_cookies = [
            {**c, 'expiry': 0} for c in cookies
        ]

        provider = TestProvider()
        result = provider.convert_to_netscape(session_cookies)

        lines = result.split('\n')
        data_lines = [line for line in lines if line and not line.startswith('#')]

        current_time = int(time.time())
        one_year_later = current_time + 365 * 24 * 3600

        for line in data_lines:
            fields = line.split('\t')
            if len(fields) >= 7:
                expiration = int(fields[4])

                # 会话Cookie应该获得大约1年后的过期时间
                # 允许一些误差（测试执行时间）
                assert expiration >= current_time, \
                    f"Expiry should be in the future, got {expiration}"
                assert expiration <= one_year_later + 60, \
                    f"Expiry should be within 1 year, got {expiration}"

    @given(cookies=cookies_list_strategy)
    @settings(max_examples=100, deadline=None)
    def test_domain_flag_correctness(self, cookies):
        """
        Property 1.5: domain flag正确设置

        *For any* cookie, if the domain starts with '.', the flag SHALL be TRUE,
        otherwise it SHALL be FALSE.

        **Validates: Requirements 7.2**
        """
        provider = TestProvider()
        result = provider.convert_to_netscape(cookies)

        lines = result.split('\n')
        data_lines = [line for line in lines if line and not line.startswith('#')]

        for line in data_lines:
            fields = line.split('\t')
            if len(fields) >= 7:
                domain = fields[0]
                flag = fields[1]

                if domain.startswith('.'):
                    assert flag == 'TRUE', \
                        f"Flag should be TRUE for domain {domain}, got {flag}"
                else:
                    assert flag == 'FALSE', \
                        f"Flag should be FALSE for domain {domain}, got {flag}"

    def test_empty_cookies_list(self):
        """测试空Cookie列表"""
        provider = TestProvider()
        result = provider.convert_to_netscape([])

        lines = result.split('\n')
        data_lines = [line for line in lines if line and not line.startswith('#')]

        assert len(data_lines) == 0, "Empty cookie list should produce no data lines"

    def test_invalid_cookies_skipped(self):
        """测试无效Cookie被跳过"""
        provider = TestProvider()

        invalid_cookies = [
            {'name': '', 'value': 'test', 'domain': '.test.com'},  # 空name
            {'name': 'test', 'value': 'test', 'domain': ''},  # 空domain
            {'value': 'test', 'domain': '.test.com'},  # 缺少name
        ]

        result = provider.convert_to_netscape(invalid_cookies)

        lines = result.split('\n')
        data_lines = [line for line in lines if line and not line.startswith('#')]

        # 所有无效Cookie都应该被跳过
        assert len(data_lines) == 0, "Invalid cookies should be skipped"

    def test_netscape_header_present(self):
        """测试Netscape文件头存在"""
        provider = TestProvider()

        cookies = [
            {'name': 'test', 'value': 'value', 'domain': '.test.com', 'path': '/'}
        ]

        result = provider.convert_to_netscape(cookies)

        assert result.startswith('# Netscape HTTP Cookie File'), \
            "Result should start with Netscape header"


# ============ 边界情况测试 ============

class TestCookieConversionEdgeCases:
    """Cookie转换边界情况测试"""

    def test_special_characters_in_value(self):
        """测试值中的特殊字符"""
        provider = TestProvider()

        cookies = [
            {
                'name': 'test',
                'value': 'value with spaces and=equals&ampersand',
                'domain': '.test.com',
                'path': '/'
            }
        ]

        result = provider.convert_to_netscape(cookies)

        lines = result.split('\n')
        data_lines = [line for line in lines if line and not line.startswith('#')]

        assert len(data_lines) == 1
        fields = data_lines[0].split('\t')
        assert fields[6] == 'value with spaces and=equals&ampersand'

    def test_unicode_in_value(self):
        """测试值中的Unicode字符"""
        provider = TestProvider()

        cookies = [
            {
                'name': 'test',
                'value': '中文值测试',
                'domain': '.test.com',
                'path': '/'
            }
        ]

        result = provider.convert_to_netscape(cookies)

        lines = result.split('\n')
        data_lines = [line for line in lines if line and not line.startswith('#')]

        assert len(data_lines) == 1
        fields = data_lines[0].split('\t')
        assert fields[6] == '中文值测试'

    def test_very_long_value(self):
        """测试非常长的Cookie值"""
        provider = TestProvider()

        long_value = 'x' * 4000  # 4KB值
        cookies = [
            {
                'name': 'test',
                'value': long_value,
                'domain': '.test.com',
                'path': '/'
            }
        ]

        result = provider.convert_to_netscape(cookies)

        lines = result.split('\n')
        data_lines = [line for line in lines if line and not line.startswith('#')]

        assert len(data_lines) == 1
        fields = data_lines[0].split('\t')
        assert fields[6] == long_value
