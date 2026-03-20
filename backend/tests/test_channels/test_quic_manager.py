"""
QUIC管理器属性测试

Property 6: QUIC Selective Blocking
Validates: Requirements 4.1, 4.4
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, patch, MagicMock
from typing import List, Set
import asyncio

from src.core.channels.quic_manager import QUICManager, QUICBlockStats


# Helper function to run async code in tests
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
def port_strategy(draw):
    """生成有效端口号"""
    return draw(st.integers(min_value=1024, max_value=65535))


@st.composite
def ip_address_strategy(draw):
    """生成随机IP地址"""
    octets = [draw(st.integers(min_value=0, max_value=255)) for _ in range(4)]
    return ".".join(str(o) for o in octets)


@st.composite
def packet_info_strategy(draw):
    """生成随机数据包信息"""
    return {
        "src_port": draw(port_strategy()),
        "dst_ip": draw(ip_address_strategy()),
        "dst_port": draw(st.sampled_from([443, 80, 8080, 8443, 53])),
        "protocol": draw(st.sampled_from(["udp", "tcp", "UDP", "TCP"])),
    }


@st.composite
def wechat_port_set_strategy(draw):
    """生成微信进程端口集合"""
    num_ports = draw(st.integers(min_value=0, max_value=10))
    ports = set()
    for _ in range(num_ports):
        ports.add(draw(port_strategy()))
    return ports


# ============================================================================
# Property 6: QUIC Selective Blocking
# Validates: Requirements 4.1, 4.4
# ============================================================================

class TestQUICSelectiveBlocking:
    """
    Property 6: QUIC Selective Blocking

    For any UDP packet to port 443, the QUICManager should block it if and only if:
    (1) QUIC blocking is enabled, AND
    (2) the source port belongs to a WeChat process.
    Non-WeChat QUIC traffic should never be blocked.

    **Feature: weixin-channels-deep-research, Property 6: QUIC Selective Blocking**
    **Validates: Requirements 4.1, 4.4**
    """

    @given(packet=packet_info_strategy(), wechat_ports=wechat_port_set_strategy())
    @settings(max_examples=100)
    def test_quic_blocking_conditions(self, packet, wechat_ports):
        """测试QUIC阻止条件

        Property: 仅当以下所有条件满足时才阻止包：
        1. QUIC阻止已启用
        2. 协议为UDP
        3. 目标端口为443
        4. 源端口属于微信进程
        """
        manager = QUICManager()

        # 模拟微信端口
        manager._port_to_pid = {port: 1000 for port in wechat_ports}
        manager._wechat_pids = {1000} if wechat_ports else set()

        src_port = packet["src_port"]
        dst_ip = packet["dst_ip"]
        dst_port = packet["dst_port"]
        protocol = packet["protocol"]

        is_wechat_port = src_port in wechat_ports
        is_udp = protocol.lower() == "udp"
        is_quic_port = dst_port == 443

        # 测试阻止禁用时
        manager._is_blocking = False
        result = manager.should_block_packet(src_port, dst_ip, dst_port, protocol)
        assert result is False, "Should not block when blocking is disabled"

        # 测试阻止启用时
        manager._is_blocking = True
        result = manager.should_block_packet(src_port, dst_ip, dst_port, protocol)

        expected = is_udp and is_quic_port and is_wechat_port
        assert result == expected, \
            f"Expected {expected}, got {result} for packet {packet}, wechat_ports={wechat_ports}"

    @given(src_port=port_strategy(), dst_ip=ip_address_strategy())
    @settings(max_examples=100)
    def test_non_wechat_traffic_never_blocked(self, src_port, dst_ip):
        """测试非微信流量永不被阻止

        Property: 非微信进程的QUIC流量永远不应该被阻止。
        """
        manager = QUICManager()
        manager._is_blocking = True

        # 确保端口不属于微信进程
        manager._port_to_pid = {}
        manager._wechat_pids = set()

        # 即使是UDP 443，也不应该阻止
        result = manager.should_block_packet(src_port, dst_ip, 443, "udp")
        assert result is False, "Non-WeChat QUIC traffic should never be blocked"

    @given(src_port=port_strategy(), dst_ip=ip_address_strategy(),
           dst_port=st.integers(min_value=1, max_value=65535).filter(lambda x: x != 443))
    @settings(max_examples=100)
    def test_non_quic_port_never_blocked(self, src_port, dst_ip, dst_port):
        """测试非QUIC端口永不被阻止

        Property: 非443端口的UDP流量永远不应该被阻止。
        """
        manager = QUICManager()
        manager._is_blocking = True

        # 即使是微信进程的端口
        manager._port_to_pid = {src_port: 1000}
        manager._wechat_pids = {1000}

        result = manager.should_block_packet(src_port, dst_ip, dst_port, "udp")
        assert result is False, f"Non-QUIC port {dst_port} should never be blocked"

    @given(src_port=port_strategy(), dst_ip=ip_address_strategy())
    @settings(max_examples=100)
    def test_tcp_traffic_never_blocked(self, src_port, dst_ip):
        """测试TCP流量永不被阻止

        Property: TCP流量永远不应该被阻止，即使是443端口。
        """
        manager = QUICManager()
        manager._is_blocking = True

        # 即使是微信进程的端口
        manager._port_to_pid = {src_port: 1000}
        manager._wechat_pids = {1000}

        result = manager.should_block_packet(src_port, dst_ip, 443, "tcp")
        assert result is False, "TCP traffic should never be blocked"

    def test_wechat_quic_traffic_blocked(self):
        """测试微信QUIC流量被阻止"""
        manager = QUICManager()
        manager._is_blocking = True

        # 设置微信端口
        wechat_port = 12345
        manager._port_to_pid = {wechat_port: 1000}
        manager._wechat_pids = {1000}

        result = manager.should_block_packet(wechat_port, "1.2.3.4", 443, "udp")
        assert result is True, "WeChat QUIC traffic should be blocked"

    def test_blocking_disabled_by_default(self):
        """测试默认情况下阻止是禁用的"""
        manager = QUICManager()
        assert manager.is_blocking is False
        assert manager._is_blocking is False


# ============================================================================
# Additional Unit Tests
# ============================================================================

class TestQUICManagerBasics:
    """QUIC管理器基础测试"""

    def test_default_target_processes(self):
        """测试默认目标进程列表"""
        manager = QUICManager()

        expected_processes = [
            "WeChat.exe",
            "WeChatAppEx.exe",
            "WeChatApp.exe",
            "WeChatBrowser.exe",
            "WeChatPlayer.exe",
            "Weixin.exe",
            "WXWork.exe",
        ]

        for proc in expected_processes:
            assert proc in manager.target_processes, f"Missing default process: {proc}"

    def test_custom_target_processes(self):
        """测试自定义目标进程列表"""
        custom_processes = ["CustomApp.exe", "AnotherApp.exe"]
        manager = QUICManager(target_processes=custom_processes)

        assert manager.target_processes == custom_processes

    def test_add_target_process(self):
        """测试添加目标进程"""
        manager = QUICManager(target_processes=["WeChat.exe"])

        manager.add_target_process("NewApp.exe")
        assert "NewApp.exe" in manager.target_processes

        # 不应该重复添加
        manager.add_target_process("NewApp.exe")
        assert manager.target_processes.count("NewApp.exe") == 1

    def test_remove_target_process(self):
        """测试移除目标进程"""
        manager = QUICManager(target_processes=["WeChat.exe", "WeChatAppEx.exe"])

        manager.remove_target_process("WeChat.exe")
        assert "WeChat.exe" not in manager.target_processes
        assert "WeChatAppEx.exe" in manager.target_processes

    def test_get_target_processes_returns_copy(self):
        """测试获取目标进程返回副本"""
        manager = QUICManager(target_processes=["WeChat.exe"])

        processes = manager.get_target_processes()
        processes.append("Modified.exe")

        assert "Modified.exe" not in manager.target_processes

    def test_quic_port_constant(self):
        """测试QUIC端口常量"""
        assert QUICManager.QUIC_PORT == 443


class TestQUICBlockStats:
    """QUIC阻止统计测试"""

    def test_initial_stats(self):
        """测试初始统计值"""
        manager = QUICManager()
        stats = manager.get_stats()

        assert stats.packets_blocked == 0
        assert stats.packets_allowed == 0
        assert stats.last_blocked_at is None
        assert len(stats.blocked_ports) == 0

    def test_stats_update_on_block(self):
        """测试阻止时统计更新"""
        manager = QUICManager()
        manager._is_blocking = True

        # 设置微信端口
        wechat_port = 12345
        manager._port_to_pid = {wechat_port: 1000}
        manager._wechat_pids = {1000}

        # 阻止一个包
        manager.should_block_packet(wechat_port, "1.2.3.4", 443, "udp")

        stats = manager.get_stats()
        assert stats.packets_blocked == 1
        assert stats.last_blocked_at is not None
        assert wechat_port in stats.blocked_ports

    def test_stats_update_on_allow(self):
        """测试允许时统计更新"""
        manager = QUICManager()
        manager._is_blocking = True

        # 非微信端口
        manager._port_to_pid = {}
        manager._wechat_pids = set()

        # 允许一个包
        manager.should_block_packet(12345, "1.2.3.4", 443, "udp")

        stats = manager.get_stats()
        assert stats.packets_allowed == 1
        assert stats.packets_blocked == 0

    def test_get_blocked_count(self):
        """测试获取阻止计数"""
        manager = QUICManager()
        manager._is_blocking = True

        wechat_port = 12345
        manager._port_to_pid = {wechat_port: 1000}
        manager._wechat_pids = {1000}

        assert manager.get_blocked_count() == 0

        manager.should_block_packet(wechat_port, "1.2.3.4", 443, "udp")
        assert manager.get_blocked_count() == 1

        manager.should_block_packet(wechat_port, "1.2.3.4", 443, "udp")
        assert manager.get_blocked_count() == 2

    def test_reset_stats(self):
        """测试重置统计"""
        manager = QUICManager()
        manager._is_blocking = True

        wechat_port = 12345
        manager._port_to_pid = {wechat_port: 1000}
        manager._wechat_pids = {1000}

        manager.should_block_packet(wechat_port, "1.2.3.4", 443, "udp")
        assert manager.get_blocked_count() == 1

        manager.reset_stats()

        stats = manager.get_stats()
        assert stats.packets_blocked == 0
        assert stats.packets_allowed == 0
        assert stats.last_blocked_at is None

    def test_stats_to_dict(self):
        """测试统计转换为字典"""
        stats = QUICBlockStats(
            packets_blocked=10,
            packets_allowed=20,
        )

        d = stats.to_dict()
        assert d["packets_blocked"] == 10
        assert d["packets_allowed"] == 20
        assert "last_blocked_at" in d
        assert "blocked_ports" in d


class TestProcessDetection:
    """进程检测测试"""

    def test_is_target_process_case_insensitive(self):
        """测试目标进程检测不区分大小写"""
        manager = QUICManager(target_processes=["WeChat.exe"])

        assert manager._is_target_process("WeChat.exe") is True
        assert manager._is_target_process("wechat.exe") is True
        assert manager._is_target_process("WECHAT.EXE") is True
        assert manager._is_target_process("WeChat.EXE") is True

    def test_is_target_process_empty_name(self):
        """测试空进程名返回False"""
        manager = QUICManager()

        assert manager._is_target_process("") is False
        assert manager._is_target_process(None) is False

    def test_is_target_process_unknown(self):
        """测试未知进程返回False"""
        manager = QUICManager(target_processes=["WeChat.exe"])

        assert manager._is_target_process("chrome.exe") is False
        assert manager._is_target_process("notepad.exe") is False


class TestAsyncOperations:
    """异步操作测试"""

    def test_start_blocking_when_already_running(self):
        """测试已运行时启动阻止"""
        manager = QUICManager()
        manager._is_blocking = True

        result = run_async(manager.start_blocking())
        assert result is True

    def test_stop_blocking_when_not_running(self):
        """测试未运行时停止阻止"""
        manager = QUICManager()
        manager._is_blocking = False

        result = run_async(manager.stop_blocking())
        assert result is True

    def test_start_and_stop_blocking(self):
        """测试启动和停止阻止"""
        manager = QUICManager()

        # 模拟WinDivert不可用
        with patch.object(manager, '_init_windivert', return_value=True):
            result = run_async(manager.start_blocking())
            assert result is True
            assert manager.is_blocking is True

            # 给任务一点时间启动
            import time
            time.sleep(0.1)

        # 停止阻止
        result = run_async(manager.stop_blocking())
        # 即使有错误，状态也应该被重置
        assert manager.is_blocking is False


class TestPacketBlockedCallback:
    """包阻止回调测试"""

    def test_callback_called_on_block(self):
        """测试阻止时调用回调"""
        callback_data = []

        def callback(src_port, dst_ip, dst_port):
            callback_data.append((src_port, dst_ip, dst_port))

        manager = QUICManager(on_packet_blocked=callback)
        manager._is_blocking = True

        wechat_port = 12345
        manager._port_to_pid = {wechat_port: 1000}
        manager._wechat_pids = {1000}

        manager.should_block_packet(wechat_port, "1.2.3.4", 443, "udp")

        assert len(callback_data) == 1
        assert callback_data[0] == (wechat_port, "1.2.3.4", 443)

    def test_callback_not_called_on_allow(self):
        """测试允许时不调用回调"""
        callback_data = []

        def callback(src_port, dst_ip, dst_port):
            callback_data.append((src_port, dst_ip, dst_port))

        manager = QUICManager(on_packet_blocked=callback)
        manager._is_blocking = True

        # 非微信端口
        manager._port_to_pid = {}
        manager._wechat_pids = set()

        manager.should_block_packet(12345, "1.2.3.4", 443, "udp")

        assert len(callback_data) == 0

    def test_callback_error_handled(self):
        """测试回调错误被处理"""
        def bad_callback(src_port, dst_ip, dst_port):
            raise ValueError("Test error")

        manager = QUICManager(on_packet_blocked=bad_callback)
        manager._is_blocking = True

        wechat_port = 12345
        manager._port_to_pid = {wechat_port: 1000}
        manager._wechat_pids = {1000}

        # 不应该抛出异常
        result = manager.should_block_packet(wechat_port, "1.2.3.4", 443, "udp")
        assert result is True  # 仍然应该阻止
