"""
Clash API监控器属性测试

Property 7: Clash API Connection Monitoring
Validates: Requirements 5.2, 5.3
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List
import asyncio
from datetime import datetime

from src.core.channels.clash_api_monitor import ClashAPIMonitor, ClashConnection


def run_async(coro):
    """Run async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def clash_connection_strategy(draw):
    """生成随机ClashConnection"""
    # 随机选择是否为视频域名
    is_video = draw(st.booleans())

    if is_video:
        host = draw(st.sampled_from([
            "finder.video.qq.com",
            "findermp.video.qq.com",
            "wxapp.tc.qq.com",
            "channels.weixin.qq.com",
            "szextshort.weixin.qq.com",
            "vd1.video.qq.com",
            "abc.tc.qq.com",
        ]))
    else:
        host = draw(st.sampled_from([
            "www.google.com",
            "api.github.com",
            "cdn.example.com",
            "static.cloudflare.com",
            "images.unsplash.com",
        ]))

    return ClashConnection(
        id=draw(st.text(min_size=8, max_size=16, alphabet="abcdef0123456789")),
        host=host,
        dst_ip=f"{draw(st.integers(1, 255))}.{draw(st.integers(0, 255))}.{draw(st.integers(0, 255))}.{draw(st.integers(1, 255))}",
        dst_port=draw(st.integers(1, 65535)),
        src_ip="127.0.0.1",
        src_port=draw(st.integers(1024, 65535)),
        network=draw(st.sampled_from(["tcp", "udp"])),
        type=draw(st.sampled_from(["HTTP", "HTTPS", "SOCKS5"])),
        rule=draw(st.sampled_from(["DIRECT", "PROXY", "REJECT"])),
        rule_payload="",
        chains=[],
        download=draw(st.integers(0, 1000000)),
        upload=draw(st.integers(0, 1000000)),
    ), is_video


@st.composite
def connection_list_strategy(draw):
    """生成随机连接列表"""
    count = draw(st.integers(0, 20))
    connections = []
    video_count = 0

    for _ in range(count):
        conn, is_video = draw(clash_connection_strategy())
        connections.append(conn)
        if is_video:
            video_count += 1

    return connections, video_count


# ============================================================================
# Property 7: Clash API Connection Monitoring
# Validates: Requirements 5.2, 5.3
# ============================================================================

class TestClashAPIConnectionMonitoring:
    """
    Property 7: Clash API Connection Monitoring

    For any Clash API connection, the ClashAPIMonitor should correctly parse
    the /connections response and extract host/SNI information. Video-related
    connections should be identified by matching against known video domain patterns.

    **Feature: weixin-channels-deep-research, Property 7: Clash API Connection Monitoring**
    **Validates: Requirements 5.2, 5.3**
    """

    @given(data=connection_list_strategy())
    @settings(max_examples=100)
    def test_video_connection_filtering(self, data):
        """测试视频连接过滤正确性

        Property: 对于任意连接列表，filter_video_connections应该只返回
        匹配视频域名模式的连接，且不遗漏任何视频连接。
        """
        connections, expected_video_count = data
        monitor = ClashAPIMonitor()

        filtered = monitor.filter_video_connections(connections)

        # 验证过滤结果
        for conn in filtered:
            assert monitor.is_video_connection(conn), \
                f"Filtered connection {conn.host} should be a video connection"

        # 验证没有遗漏
        actual_video_count = sum(1 for c in connections if monitor.is_video_connection(c))
        assert len(filtered) == actual_video_count, \
            f"Expected {actual_video_count} video connections, got {len(filtered)}"

    def test_known_video_domains_detected(self):
        """测试已知视频域名都能被检测"""
        monitor = ClashAPIMonitor()

        video_domains = [
            "finder.video.qq.com",
            "findermp.video.qq.com",
            "wxapp.tc.qq.com",
            "channels.weixin.qq.com",
            "szextshort.weixin.qq.com",
            "szvideo.weixin.qq.com",
            "vd1.video.qq.com",
            "vd2.video.qq.com",
            "abc.tc.qq.com",
        ]

        for domain in video_domains:
            conn = ClashConnection(
                id="test", host=domain, dst_ip="1.2.3.4", dst_port=443,
                src_ip="127.0.0.1", src_port=12345, network="tcp",
                type="HTTPS", rule="DIRECT", rule_payload=""
            )
            assert monitor.is_video_connection(conn), \
                f"Domain {domain} should be detected as video connection"

    def test_non_video_domains_not_detected(self):
        """测试非视频域名不会被误检测"""
        monitor = ClashAPIMonitor()

        non_video_domains = [
            "www.google.com",
            "api.github.com",
            "cdn.cloudflare.com",
            "www.baidu.com",
            "qq.com",  # 不是视频域名
            "weixin.qq.com",  # 不是视频子域名
        ]

        for domain in non_video_domains:
            conn = ClashConnection(
                id="test", host=domain, dst_ip="1.2.3.4", dst_port=443,
                src_ip="127.0.0.1", src_port=12345, network="tcp",
                type="HTTPS", rule="DIRECT", rule_payload=""
            )
            assert not monitor.is_video_connection(conn), \
                f"Domain {domain} should NOT be detected as video connection"

    def test_empty_host_not_detected(self):
        """测试空host不会被检测为视频连接"""
        monitor = ClashAPIMonitor()

        conn = ClashConnection(
            id="test", host="", dst_ip="", dst_port=443,
            src_ip="127.0.0.1", src_port=12345, network="tcp",
            type="HTTPS", rule="DIRECT", rule_payload=""
        )
        assert not monitor.is_video_connection(conn)

    def test_case_insensitive_detection(self):
        """测试域名检测不区分大小写"""
        monitor = ClashAPIMonitor()

        test_cases = [
            "FINDER.VIDEO.QQ.COM",
            "Finder.Video.QQ.Com",
            "finder.VIDEO.qq.COM",
        ]

        for domain in test_cases:
            conn = ClashConnection(
                id="test", host=domain, dst_ip="1.2.3.4", dst_port=443,
                src_ip="127.0.0.1", src_port=12345, network="tcp",
                type="HTTPS", rule="DIRECT", rule_payload=""
            )
            assert monitor.is_video_connection(conn), \
                f"Domain {domain} should be detected (case insensitive)"


class TestClashAPIMonitorConnection:
    """Clash API连接测试"""

    def test_base_url_formatting(self):
        """测试base_url格式化"""
        # 不带协议
        monitor = ClashAPIMonitor("127.0.0.1:9090")
        assert monitor.base_url == "http://127.0.0.1:9090"

        # 带http协议
        monitor = ClashAPIMonitor("http://127.0.0.1:9090")
        assert monitor.base_url == "http://127.0.0.1:9090"

        # 带https协议
        monitor = ClashAPIMonitor("https://127.0.0.1:9090")
        assert monitor.base_url == "https://127.0.0.1:9090"

    def test_headers_without_secret(self):
        """测试无密钥时的headers"""
        monitor = ClashAPIMonitor("127.0.0.1:9090")
        headers = monitor.headers

        assert "Content-Type" in headers
        assert "Authorization" not in headers

    def test_headers_with_secret(self):
        """测试有密钥时的headers"""
        monitor = ClashAPIMonitor("127.0.0.1:9090", api_secret="test_secret")
        headers = monitor.headers

        assert "Content-Type" in headers
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_secret"

    def test_initial_state(self):
        """测试初始状态"""
        monitor = ClashAPIMonitor()

        assert not monitor.is_connected
        assert monitor._session is None
        assert monitor._polling_task is None


class TestClashConnectionDataclass:
    """ClashConnection数据类测试"""

    def test_to_dict(self):
        """测试to_dict方法"""
        conn = ClashConnection(
            id="abc123",
            host="finder.video.qq.com",
            dst_ip="1.2.3.4",
            dst_port=443,
            src_ip="127.0.0.1",
            src_port=12345,
            network="tcp",
            type="HTTPS",
            rule="DIRECT",
            rule_payload="",
            chains=["PROXY"],
            download=1000,
            upload=500,
        )

        d = conn.to_dict()

        assert d["id"] == "abc123"
        assert d["host"] == "finder.video.qq.com"
        assert d["dst_ip"] == "1.2.3.4"
        assert d["dst_port"] == 443
        assert d["network"] == "tcp"
        assert d["download"] == 1000
        assert d["upload"] == 500
        assert "start" in d

    def test_default_values(self):
        """测试默认值"""
        conn = ClashConnection(
            id="test",
            host="test.com",
            dst_ip="1.2.3.4",
            dst_port=443,
            src_ip="127.0.0.1",
            src_port=12345,
            network="tcp",
            type="HTTPS",
            rule="DIRECT",
            rule_payload="",
        )

        assert conn.chains == []
        assert conn.download == 0
        assert conn.upload == 0
        assert isinstance(conn.start, datetime)
