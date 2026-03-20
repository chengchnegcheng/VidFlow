"""
Cookie提取完整性属性测试

Property 4: Cookie Extraction Completeness
*For any* successful login response from a platform, the cookie extraction logic SHALL:
- Extract all cookies set by the response
- Include both session cookies and persistent cookies
- Not lose any cookie attributes during extraction

**Validates: Requirements 1.5, 2.5, 3.5, 4.5**

使用Hypothesis进行属性测试，每个测试至少运行100次。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any, Optional
import time

from src.core.qr_login import (
    BilibiliQRProvider,
    KuaishouQRProvider,
    WeiboQRProvider,
    IqiyiQRProvider,
    MangoQRProvider,
    TencentQRProvider,
)


# ============ 测试数据生成策略 ============

# Cookie名称策略 - 生成有效的cookie名称（必须以字母开头）
cookie_name_strategy = st.text(
    alphabet=st.sampled_from('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'),
    min_size=2,
    max_size=50
).filter(lambda x: x.strip() and x[0].isalpha())

# Cookie值策略 - 生成有效的cookie值
cookie_value_strategy = st.text(
    alphabet=st.sampled_from('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-=+/'),
    min_size=0,
    max_size=200
)

# 域名策略
domain_strategy = st.sampled_from([
    '.bilibili.com',
    '.kuaishou.com',
    '.weibo.com',
    '.iqiyi.com',
    '.mgtv.com',
    '.qq.com',
    '.example.com',
])

# 路径策略
path_strategy = st.sampled_from(['/', '/api', '/user', '/login'])

# 过期时间策略 - 0表示session cookie，正数表示持久cookie
expiry_strategy = st.one_of(
    st.just(0),  # Session cookie
    st.integers(min_value=int(time.time()), max_value=2147483647)  # Persistent cookie
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
cookies_list_strategy = st.lists(
    cookie_strategy,
    min_size=1,
    max_size=20
)


# ============ 辅助函数 ============

def parse_netscape_cookies(netscape_content: str) -> List[Dict[str, Any]]:
    """解析Netscape格式的Cookie内容

    Args:
        netscape_content: Netscape格式的Cookie字符串

    Returns:
        解析后的Cookie列表
    """
    cookies = []
    for line in netscape_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        parts = line.split('\t')
        if len(parts) >= 6:  # 至少需要6个字段（值可以为空）
            cookies.append({
                'domain': parts[0],
                'flag': parts[1],
                'path': parts[2],
                'secure': parts[3].upper() == 'TRUE',
                'expiry': int(parts[4]) if parts[4].isdigit() else 0,
                'name': parts[5],
                'value': parts[6] if len(parts) > 6 else '',  # 值可能为空
            })

    return cookies


def get_all_providers():
    """获取所有Provider实例"""
    return [
        BilibiliQRProvider(),
        KuaishouQRProvider(),
        WeiboQRProvider(),
        IqiyiQRProvider(),
        MangoQRProvider(),
        TencentQRProvider(),
    ]


# ============ Property 4: Cookie Extraction Completeness ============

class TestCookieExtractionCompleteness:
    """
    Property 4: Cookie Extraction Completeness

    *For any* successful login response from a platform, the cookie extraction logic SHALL:
    - Extract all cookies set by the response
    - Include both session cookies and persistent cookies
    - Not lose any cookie attributes during extraction

    **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
    """

    @settings(max_examples=100, deadline=None)
    @given(cookies=cookies_list_strategy)
    def test_all_cookies_extracted(self, cookies: List[Dict[str, Any]]):
        """
        Property: 所有Cookie都被提取

        *For any* list of cookies, converting to Netscape format SHALL include all cookies.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            # 验证所有cookie名称都存在
            original_names = {c['name'] for c in cookies}
            parsed_names = {c['name'] for c in parsed}

            assert original_names == parsed_names, \
                f"{provider.platform_id}: Cookie名称不匹配. 原始: {original_names}, 解析: {parsed_names}"

    @settings(max_examples=100, deadline=None)
    @given(cookies=cookies_list_strategy)
    def test_session_cookies_included(self, cookies: List[Dict[str, Any]]):
        """
        Property: Session Cookie被正确包含

        *For any* list containing session cookies (expiry=0), they SHALL be included in the output.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        # 确保至少有一个session cookie
        session_cookies = [c for c in cookies if c.get('expiry', 0) == 0]
        assume(len(session_cookies) > 0)

        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            # 验证session cookies存在
            for session_cookie in session_cookies:
                found = any(
                    p['name'] == session_cookie['name']
                    for p in parsed
                )
                assert found, \
                    f"{provider.platform_id}: Session cookie '{session_cookie['name']}' 未被提取"

    @settings(max_examples=100, deadline=None)
    @given(cookies=cookies_list_strategy)
    def test_persistent_cookies_included(self, cookies: List[Dict[str, Any]]):
        """
        Property: Persistent Cookie被正确包含

        *For any* list containing persistent cookies (expiry>0), they SHALL be included in the output.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        # 确保至少有一个persistent cookie
        persistent_cookies = [c for c in cookies if c.get('expiry', 0) > 0]
        assume(len(persistent_cookies) > 0)

        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            # 验证persistent cookies存在
            for persistent_cookie in persistent_cookies:
                found = any(
                    p['name'] == persistent_cookie['name']
                    for p in parsed
                )
                assert found, \
                    f"{provider.platform_id}: Persistent cookie '{persistent_cookie['name']}' 未被提取"

    @settings(max_examples=100, deadline=None)
    @given(cookies=cookies_list_strategy)
    def test_cookie_values_preserved(self, cookies: List[Dict[str, Any]]):
        """
        Property: Cookie值被完整保留

        *For any* cookie, its value SHALL be preserved exactly during extraction.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            # 创建name->value映射
            original_values = {c['name']: c['value'] for c in cookies}
            parsed_values = {c['name']: c['value'] for c in parsed}

            for name, original_value in original_values.items():
                assert name in parsed_values, \
                    f"{provider.platform_id}: Cookie '{name}' 未找到"
                assert parsed_values[name] == original_value, \
                    f"{provider.platform_id}: Cookie '{name}' 值不匹配. 原始: '{original_value}', 解析: '{parsed_values[name]}'"

    @settings(max_examples=100, deadline=None)
    @given(cookies=cookies_list_strategy)
    def test_cookie_domains_preserved(self, cookies: List[Dict[str, Any]]):
        """
        Property: Cookie域名被完整保留

        *For any* cookie, its domain SHALL be preserved during extraction.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            # 创建name->domain映射
            original_domains = {c['name']: c['domain'] for c in cookies}
            parsed_domains = {c['name']: c['domain'] for c in parsed}

            for name, original_domain in original_domains.items():
                assert name in parsed_domains, \
                    f"{provider.platform_id}: Cookie '{name}' 未找到"
                assert parsed_domains[name] == original_domain, \
                    f"{provider.platform_id}: Cookie '{name}' 域名不匹配. 原始: '{original_domain}', 解析: '{parsed_domains[name]}'"

    @settings(max_examples=100, deadline=None)
    @given(cookies=cookies_list_strategy)
    def test_cookie_paths_preserved(self, cookies: List[Dict[str, Any]]):
        """
        Property: Cookie路径被完整保留

        *For any* cookie, its path SHALL be preserved during extraction.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            # 创建name->path映射
            original_paths = {c['name']: c['path'] for c in cookies}
            parsed_paths = {c['name']: c['path'] for c in parsed}

            for name, original_path in original_paths.items():
                assert name in parsed_paths, \
                    f"{provider.platform_id}: Cookie '{name}' 未找到"
                assert parsed_paths[name] == original_path, \
                    f"{provider.platform_id}: Cookie '{name}' 路径不匹配. 原始: '{original_path}', 解析: '{parsed_paths[name]}'"

    @settings(max_examples=100, deadline=None)
    @given(cookies=cookies_list_strategy)
    def test_cookie_secure_flag_preserved(self, cookies: List[Dict[str, Any]]):
        """
        Property: Cookie安全标志被完整保留

        *For any* cookie, its secure flag SHALL be preserved during extraction.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            # 创建name->secure映射
            original_secure = {c['name']: c['secure'] for c in cookies}
            parsed_secure = {c['name']: c['secure'] for c in parsed}

            for name, original_flag in original_secure.items():
                assert name in parsed_secure, \
                    f"{provider.platform_id}: Cookie '{name}' 未找到"
                assert parsed_secure[name] == original_flag, \
                    f"{provider.platform_id}: Cookie '{name}' secure标志不匹配. 原始: {original_flag}, 解析: {parsed_secure[name]}"

    @settings(max_examples=100, deadline=None)
    @given(cookies=cookies_list_strategy)
    def test_cookie_expiry_preserved(self, cookies: List[Dict[str, Any]]):
        """
        Property: Cookie过期时间被完整保留

        *For any* cookie with expiry > 0, its expiry time SHALL be preserved during extraction.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        # 只测试有过期时间的cookie
        persistent_cookies = [c for c in cookies if c.get('expiry', 0) > 0]
        assume(len(persistent_cookies) > 0)

        # 确保cookie名称唯一（取每个名称的第一个出现）
        seen_names = set()
        unique_persistent = []
        for c in persistent_cookies:
            if c['name'] not in seen_names:
                seen_names.add(c['name'])
                unique_persistent.append(c)

        assume(len(unique_persistent) > 0)

        for provider in get_all_providers():
            result = provider.convert_to_netscape(unique_persistent)
            parsed = parse_netscape_cookies(result)

            # 创建name->expiry映射
            original_expiry = {c['name']: c['expiry'] for c in unique_persistent}
            parsed_expiry = {c['name']: c['expiry'] for c in parsed}

            for name, original_exp in original_expiry.items():
                assert name in parsed_expiry, \
                    f"{provider.platform_id}: Cookie '{name}' 未找到"
                assert parsed_expiry[name] == original_exp, \
                    f"{provider.platform_id}: Cookie '{name}' 过期时间不匹配. 原始: {original_exp}, 解析: {parsed_expiry[name]}"


class TestCookieExtractionEdgeCases:
    """Cookie提取边缘情况测试"""

    @settings(max_examples=100, deadline=None)
    @given(
        name=st.text(
            alphabet=st.sampled_from('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'),
            min_size=2,
            max_size=50
        ).filter(lambda x: x.strip() and x[0].isalpha()),
        value=st.text(min_size=0, max_size=500)
    )
    def test_special_characters_in_value(self, name: str, value: str):
        """
        Property: 特殊字符在值中被正确处理

        *For any* cookie value containing special characters, extraction SHALL handle them correctly.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        # 过滤掉包含制表符、换行符的值（这些会破坏Netscape格式）
        # 也过滤掉纯空格的值（会被strip）
        assume('\t' not in value and '\n' not in value and '\r' not in value)
        assume(value.strip() == value or value == '')  # 值不应该有前后空格，除非是空字符串

        cookies = [{
            'name': name,
            'value': value,
            'domain': '.example.com',
            'path': '/',
            'secure': True,
            'expiry': 1735689600,
        }]

        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            assert len(parsed) == 1, f"{provider.platform_id}: 应该有1个cookie"
            assert parsed[0]['name'] == name
            assert parsed[0]['value'] == value

    @settings(max_examples=100, deadline=None)
    @given(count=st.integers(min_value=1, max_value=50))
    def test_multiple_cookies_all_extracted(self, count: int):
        """
        Property: 多个Cookie全部被提取

        *For any* number of cookies, all SHALL be extracted.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        cookies = [
            {
                'name': f'cookie_{i}',
                'value': f'value_{i}',
                'domain': '.example.com',
                'path': '/',
                'secure': i % 2 == 0,
                'expiry': 1735689600 if i % 3 == 0 else 0,
            }
            for i in range(count)
        ]

        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            assert len(parsed) == count, \
                f"{provider.platform_id}: 应该有{count}个cookie，实际有{len(parsed)}个"

    def test_empty_cookie_list(self):
        """测试空Cookie列表"""
        cookies = []

        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            assert len(parsed) == 0, f"{provider.platform_id}: 空列表应该返回0个cookie"

    @settings(max_examples=100, deadline=None)
    @given(
        session_count=st.integers(min_value=1, max_value=10),
        persistent_count=st.integers(min_value=1, max_value=10)
    )
    def test_mixed_session_and_persistent_cookies(self, session_count: int, persistent_count: int):
        """
        Property: 混合Session和Persistent Cookie都被正确提取

        *For any* mix of session and persistent cookies, all SHALL be extracted.

        **Feature: multi-platform-qr-login, Property 4: Cookie Extraction Completeness**
        **Validates: Requirements 1.5, 2.5, 3.5, 4.5**
        """
        cookies = []

        # 添加session cookies
        for i in range(session_count):
            cookies.append({
                'name': f'session_{i}',
                'value': f'session_value_{i}',
                'domain': '.example.com',
                'path': '/',
                'secure': True,
                'expiry': 0,  # Session cookie
            })

        # 添加persistent cookies
        for i in range(persistent_count):
            cookies.append({
                'name': f'persistent_{i}',
                'value': f'persistent_value_{i}',
                'domain': '.example.com',
                'path': '/',
                'secure': True,
                'expiry': 1735689600,  # Persistent cookie
            })

        total_count = session_count + persistent_count

        for provider in get_all_providers():
            result = provider.convert_to_netscape(cookies)
            parsed = parse_netscape_cookies(result)

            assert len(parsed) == total_count, \
                f"{provider.platform_id}: 应该有{total_count}个cookie，实际有{len(parsed)}个"

            # 验证session cookies
            session_names = {f'session_{i}' for i in range(session_count)}
            parsed_session = {c['name'] for c in parsed if c['name'].startswith('session_')}
            assert session_names == parsed_session, \
                f"{provider.platform_id}: Session cookies不匹配"

            # 验证persistent cookies
            persistent_names = {f'persistent_{i}' for i in range(persistent_count)}
            parsed_persistent = {c['name'] for c in parsed if c['name'].startswith('persistent_')}
            assert persistent_names == parsed_persistent, \
                f"{provider.platform_id}: Persistent cookies不匹配"
