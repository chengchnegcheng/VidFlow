"""
ECH处理器属性测试

Property 5: ECH Detection and IP Fallback
Validates: Requirements 3.1, 3.2, 3.4
"""

import pytest
from hypothesis import given, strategies as st, settings
from typing import List
import ipaddress

from src.core.channels.ech_handler import ECHHandler, TLSInfo


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def ip_in_range_strategy(draw):
    """生成腾讯CDN范围内的IP"""
    # 从已知范围中选择一个
    ranges = [
        ("183.3.0.0", "183.3.255.255"),
        ("183.47.0.0", "183.47.255.255"),
        ("14.17.0.0", "14.17.255.255"),
        ("113.96.0.0", "113.96.255.255"),
        ("203.205.0.0", "203.205.255.255"),
    ]
    
    range_start, range_end = draw(st.sampled_from(ranges))
    start_parts = [int(x) for x in range_start.split(".")]
    
    # 生成范围内的IP
    return f"{start_parts[0]}.{start_parts[1]}.{draw(st.integers(0, 255))}.{draw(st.integers(1, 254))}"


@st.composite
def ip_outside_range_strategy(draw):
    """生成腾讯CDN范围外的IP"""
    # 使用明显不在范围内的IP段
    first_octet = draw(st.sampled_from([8, 9, 10, 172, 192, 1, 2, 3]))
    return f"{first_octet}.{draw(st.integers(0, 255))}.{draw(st.integers(0, 255))}.{draw(st.integers(1, 254))}"


@st.composite
def valid_sni_strategy(draw):
    """生成有效的SNI域名"""
    subdomain = draw(st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"))
    domain = draw(st.sampled_from(["qq.com", "weixin.qq.com", "video.qq.com", "example.com"]))
    return f"{subdomain}.{domain}"


# ============================================================================
# Property 5: ECH Detection and IP Fallback
# Validates: Requirements 3.1, 3.2, 3.4
# ============================================================================

class TestECHDetectionAndIPFallback:
    """
    Property 5: ECH Detection and IP Fallback
    
    For any TLS ClientHello packet, the ECHHandler should correctly detect
    the presence of ECH extension. When ECH is detected and SNI cannot be
    extracted, the system should fall back to IP-based identification using
    the known video server IP database.
    
    **Feature: weixin-channels-deep-research, Property 5: ECH Detection and IP Fallback**
    **Validates: Requirements 3.1, 3.2, 3.4**
    """

    @given(ip=ip_in_range_strategy())
    @settings(max_examples=100)
    def test_video_server_ip_detection(self, ip):
        """测试视频服务器IP检测
        
        Property: 对于任意腾讯CDN范围内的IP，is_video_server_ip应返回True
        """
        handler = ECHHandler()
        assert handler.is_video_server_ip(ip), \
            f"IP {ip} should be detected as video server IP"

    @given(ip=ip_outside_range_strategy())
    @settings(max_examples=100)
    def test_non_video_server_ip_detection(self, ip):
        """测试非视频服务器IP检测
        
        Property: 对于任意不在腾讯CDN范围内的IP，is_video_server_ip应返回False
        """
        handler = ECHHandler()
        # 验证IP确实不在范围内
        ip_addr = ipaddress.ip_address(ip)
        in_range = False
        for cidr in handler.TENCENT_CDN_RANGES:
            network = ipaddress.ip_network(cidr, strict=False)
            if ip_addr in network:
                in_range = True
                break
        
        if not in_range:
            assert not handler.is_video_server_ip(ip), \
                f"IP {ip} should NOT be detected as video server IP"

    def test_known_tencent_ips_detected(self):
        """测试已知腾讯IP都能被检测"""
        handler = ECHHandler()
        
        known_ips = [
            "183.3.1.1",
            "183.47.100.50",
            "14.17.50.100",
            "113.96.200.1",
            "203.205.128.64",
            "182.254.10.20",
        ]
        
        for ip in known_ips:
            assert handler.is_video_server_ip(ip), \
                f"Known Tencent IP {ip} should be detected"

    def test_private_ips_not_detected(self):
        """测试私有IP不会被检测为视频服务器"""
        handler = ECHHandler()
        
        private_ips = [
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "127.0.0.1",
        ]
        
        for ip in private_ips:
            assert not handler.is_video_server_ip(ip), \
                f"Private IP {ip} should NOT be detected as video server"

    def test_invalid_ip_returns_false(self):
        """测试无效IP返回False"""
        handler = ECHHandler()
        
        invalid_ips = [
            "not.an.ip",
            "256.1.1.1",
            "",
            "abc",
            "1.2.3.4.5",
        ]
        
        for ip in invalid_ips:
            assert not handler.is_video_server_ip(ip), \
                f"Invalid IP {ip} should return False"


class TestTLSParsing:
    """TLS解析测试"""

    def test_parse_valid_client_hello_with_sni(self):
        """测试解析带SNI的ClientHello"""
        # 构造一个简单的ClientHello
        # 这是一个最小化的ClientHello结构
        sni = b"example.com"
        sni_ext = bytes([
            0x00, 0x00,  # SNI extension type
            0x00, len(sni) + 5,  # extension length
            0x00, len(sni) + 3,  # SNI list length
            0x00,  # host_name type
            0x00, len(sni),  # name length
        ]) + sni
        
        # 简化的ClientHello
        client_hello = bytes([
            0x03, 0x03,  # version TLS 1.2
        ]) + bytes(32) + bytes([  # random
            0x00,  # session ID length
            0x00, 0x02, 0x00, 0x2f,  # cipher suites (1 suite)
            0x01, 0x00,  # compression methods
            0x00, len(sni_ext),  # extensions length
        ]) + sni_ext
        
        # Handshake header
        handshake = bytes([
            0x01,  # ClientHello
            0x00, (len(client_hello) >> 8) & 0xff, len(client_hello) & 0xff,
        ]) + client_hello
        
        # TLS record
        tls_record = bytes([
            0x16,  # Handshake
            0x03, 0x01,  # TLS 1.0
            (len(handshake) >> 8) & 0xff, len(handshake) & 0xff,
        ]) + handshake
        
        info = ECHHandler.parse_tls_client_hello(tls_record)
        
        assert info is not None
        assert info.sni == "example.com"
        assert not info.has_ech

    def test_parse_invalid_data_returns_none(self):
        """测试解析无效数据返回None"""
        invalid_data = [
            b"",
            b"\x00",
            b"\x16\x03\x01",  # 太短
            b"\x17\x03\x01\x00\x05hello",  # 不是Handshake
        ]
        
        for data in invalid_data:
            info = ECHHandler.parse_tls_client_hello(data)
            assert info is None, f"Invalid data should return None"

    def test_has_ech_extension_with_invalid_data(self):
        """测试has_ech_extension处理无效数据"""
        assert not ECHHandler.has_ech_extension(b"")
        assert not ECHHandler.has_ech_extension(b"invalid")


class TestIPRangeManagement:
    """IP段管理测试"""

    def test_get_ip_ranges(self):
        """测试获取IP段列表"""
        handler = ECHHandler()
        ranges = handler.get_ip_ranges()
        
        assert len(ranges) > 0
        assert "183.3.0.0/16" in ranges

    def test_add_ip_range(self):
        """测试添加IP段"""
        handler = ECHHandler()
        
        # 添加新IP段
        assert handler.add_ip_range("8.8.8.0/24")
        assert handler.is_video_server_ip("8.8.8.1")

    def test_add_invalid_ip_range(self):
        """测试添加无效IP段"""
        handler = ECHHandler()
        
        assert not handler.add_ip_range("invalid")
        assert not handler.add_ip_range("256.0.0.0/8")

    def test_remove_ip_range(self):
        """测试移除IP段"""
        handler = ECHHandler()
        
        # 先添加再移除
        handler.add_ip_range("8.8.8.0/24")
        assert handler.is_video_server_ip("8.8.8.1")
        
        assert handler.remove_ip_range("8.8.8.0/24")
        assert not handler.is_video_server_ip("8.8.8.1")


class TestConnectionIdentification:
    """连接识别测试"""

    def test_identify_by_ip(self):
        """测试通过IP识别"""
        handler = ECHHandler()
        
        result = handler.identify_connection(b"", "183.3.1.1")
        
        assert result["identified"]
        assert result["method"] == "ip"
        assert result["is_video_ip"]

    def test_identify_unknown_ip(self):
        """测试未知IP"""
        handler = ECHHandler()
        
        result = handler.identify_connection(b"", "8.8.8.8")
        
        assert not result["identified"]
        assert result["method"] is None


class TestTLSInfoDataclass:
    """TLSInfo数据类测试"""

    def test_to_dict(self):
        """测试to_dict方法"""
        info = TLSInfo(
            has_ech=True,
            sni="example.com",
            ech_config_id=b"\x00\x01",
            cipher_suites=[0x1301, 0x1302],
            tls_version=0x0303,
        )
        
        d = info.to_dict()
        
        assert d["has_ech"] is True
        assert d["sni"] == "example.com"
        assert d["ech_config_id"] == "0001"
        assert d["cipher_suites"] == [0x1301, 0x1302]
        assert d["tls_version"] == 0x0303

    def test_to_dict_with_none_values(self):
        """测试to_dict处理None值"""
        info = TLSInfo(
            has_ech=False,
            sni=None,
            ech_config_id=None,
            cipher_suites=[],
            tls_version=0x0301,
        )
        
        d = info.to_dict()
        
        assert d["sni"] is None
        assert d["ech_config_id"] is None
