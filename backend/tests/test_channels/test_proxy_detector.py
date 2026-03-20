"""
代理检测器属性测试

Property 1: Proxy Detection Correctness
Property 2: Proxy Mode Detection Accuracy
Validates: Requirements 1.1, 1.2, 1.6
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Optional
import asyncio

from src.core.channels.proxy_detector import ProxyDetector
from src.core.channels.models import ProxyType, ProxyMode, ProxyInfo


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
def process_list_strategy(draw):
    """生成随机进程列表

    生成包含已知代理进程和随机进程的列表。
    """
    # 所有已知代理进程名
    known_proxy_processes = []
    for proxy_type, process_names in ProxyDetector.PROXY_PROCESSES.items():
        for name in process_names:
            known_proxy_processes.append((name, proxy_type))

    # 随机非代理进程名
    random_processes = draw(st.lists(
        st.text(min_size=1, max_size=30).filter(
            lambda x: x.strip() and '\x00' not in x and '.exe' not in x.lower()
        ).map(lambda x: x + ".exe"),
        min_size=0, max_size=20
    ))

    # 可能包含一个已知代理进程
    include_proxy = draw(st.booleans())
    proxy_process = None
    expected_type = ProxyType.NONE

    if include_proxy and known_proxy_processes:
        proxy_process, expected_type = draw(st.sampled_from(known_proxy_processes))
        random_processes.append(proxy_process)

    # 打乱顺序
    draw(st.randoms()).shuffle(random_processes)

    return random_processes, proxy_process, expected_type


@st.composite
def proxy_type_strategy(draw):
    """生成随机代理类型"""
    return draw(st.sampled_from(list(ProxyType)))


@st.composite
def network_config_strategy(draw):
    """生成随机网络配置

    用于测试代理模式检测。
    """
    return {
        "system_proxy_enabled": draw(st.booleans()),
        "tun_enabled": draw(st.booleans()),
        "fake_ip_enabled": draw(st.booleans()),
    }


# ============================================================================
# Property 1: Proxy Detection Correctness
# Validates: Requirements 1.1, 1.2, 1.6
# ============================================================================

class TestProxyDetectionCorrectness:
    """
    Property 1: Proxy Detection Correctness

    For any system with running processes, the ProxyDetector should correctly
    identify proxy software by matching process names against known patterns,
    and should return ProxyType.NONE only when no proxy processes are found.

    **Feature: weixin-channels-deep-research, Property 1: Proxy Detection Correctness**
    **Validates: Requirements 1.1, 1.2, 1.6**
    """

    @given(process_data=process_list_strategy())
    @settings(max_examples=100)
    def test_proxy_detection_from_process_list(self, process_data):
        """测试从进程列表中正确检测代理软件

        Property: 对于任意进程列表，如果包含已知代理进程，则应检测到对应的代理类型；
        如果不包含任何已知代理进程，则应返回 ProxyType.NONE。
        """
        process_list, proxy_process, expected_type = process_data

        # 创建 mock 进程迭代器
        mock_processes = []
        for i, proc_name in enumerate(process_list):
            mock_proc = Mock()
            mock_proc.info = {'pid': 1000 + i, 'name': proc_name}
            mock_processes.append(mock_proc)

        detector = ProxyDetector()

        with patch('src.core.channels.proxy_detector.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = mock_processes

            detected_type, detected_name, detected_pid = detector._scan_proxy_processes()

            if proxy_process is not None:
                # 如果进程列表包含已知代理进程，应该检测到
                assert detected_type == expected_type, \
                    f"Expected {expected_type}, got {detected_type} for process {proxy_process}"
                assert detected_name is not None
                assert detected_pid is not None
            else:
                # 如果进程列表不包含已知代理进程，应该返回 NONE
                assert detected_type == ProxyType.NONE, \
                    f"Expected NONE, got {detected_type}"

    def test_known_proxy_processes_detected(self):
        """测试所有已知代理进程都能被正确检测"""
        detector = ProxyDetector()

        for proxy_type, process_names in ProxyDetector.PROXY_PROCESSES.items():
            for proc_name in process_names:
                detected = ProxyDetector.get_proxy_type_from_process_name(proc_name)
                assert detected == proxy_type, \
                    f"Process {proc_name} should be detected as {proxy_type}, got {detected}"

    def test_unknown_process_returns_none(self):
        """测试未知进程返回 NONE"""
        unknown_processes = [
            "notepad.exe",
            "chrome.exe",
            "firefox.exe",
            "explorer.exe",
            "python.exe",
            "node.exe",
            "random_app.exe",
        ]

        for proc_name in unknown_processes:
            detected = ProxyDetector.get_proxy_type_from_process_name(proc_name)
            assert detected == ProxyType.NONE, \
                f"Unknown process {proc_name} should return NONE, got {detected}"

    def test_case_insensitive_detection(self):
        """测试进程名检测不区分大小写"""
        test_cases = [
            ("CLASH.EXE", ProxyType.CLASH),
            ("Clash.exe", ProxyType.CLASH),
            ("clash.EXE", ProxyType.CLASH),
            ("MIHOMO.EXE", ProxyType.CLASH_META),
            ("V2RAY.EXE", ProxyType.V2RAY),
        ]

        for proc_name, expected_type in test_cases:
            detected = ProxyDetector.get_proxy_type_from_process_name(proc_name)
            assert detected == expected_type, \
                f"Process {proc_name} should be detected as {expected_type}, got {detected}"

    def test_empty_process_name_returns_none(self):
        """测试空进程名返回 NONE"""
        assert ProxyDetector.get_proxy_type_from_process_name("") == ProxyType.NONE
        assert ProxyDetector.get_proxy_type_from_process_name(None) == ProxyType.NONE

    def test_no_psutil_returns_none(self):
        """测试 psutil 不可用时返回 NONE"""
        detector = ProxyDetector()

        with patch('src.core.channels.proxy_detector.HAS_PSUTIL', False):
            detected_type, detected_name, detected_pid = detector._scan_proxy_processes()
            assert detected_type == ProxyType.NONE
            assert detected_name is None
            assert detected_pid is None


# ============================================================================
# Property 2: Proxy Mode Detection Accuracy
# Validates: Requirements 1.2, 1.4
# ============================================================================

class TestProxyModeDetectionAccuracy:
    """
    Property 2: Proxy Mode Detection Accuracy

    For any detected proxy software, the system should correctly identify its
    operating mode (TUN/System Proxy/Fake-IP) based on network configuration
    and proxy settings.

    **Feature: weixin-channels-deep-research, Property 2: Proxy Mode Detection Accuracy**
    **Validates: Requirements 1.2, 1.4**
    """

    @given(config=network_config_strategy(), proxy_type=proxy_type_strategy())
    @settings(max_examples=100)
    def test_proxy_mode_detection_priority(self, config, proxy_type):
        """测试代理模式检测优先级

        Property: 代理模式检测应遵循以下优先级：
        1. 系统代理 > TUN > Fake-IP > Rule
        """
        detector = ProxyDetector()

        with patch.object(detector, '_is_system_proxy_enabled', return_value=config["system_proxy_enabled"]):
            with patch.object(detector, '_is_tun_mode_enabled', return_value=config["tun_enabled"]):
                with patch.object(detector, '_is_fake_ip_enabled', return_value=config["fake_ip_enabled"]):
                    # 运行异步方法
                    mode = run_async(detector.detect_proxy_mode(proxy_type))

                    # 验证优先级
                    if config["system_proxy_enabled"]:
                        assert mode == ProxyMode.SYSTEM_PROXY, \
                            f"System proxy enabled should return SYSTEM_PROXY, got {mode}"
                    elif config["tun_enabled"]:
                        assert mode == ProxyMode.TUN, \
                            f"TUN enabled should return TUN, got {mode}"
                    elif config["fake_ip_enabled"] and detector.is_clash_type(proxy_type):
                        assert mode == ProxyMode.FAKE_IP, \
                            f"Fake-IP enabled for Clash should return FAKE_IP, got {mode}"
                    else:
                        assert mode == ProxyMode.RULE, \
                            f"Default should return RULE, got {mode}"

    def test_system_proxy_detection_priority(self):
        """测试系统代理检测优先级最高"""
        detector = ProxyDetector()

        # 即使 TUN 和 Fake-IP 都启用，系统代理优先
        with patch.object(detector, '_is_system_proxy_enabled', return_value=True):
            with patch.object(detector, '_is_tun_mode_enabled', return_value=True):
                with patch.object(detector, '_is_fake_ip_enabled', return_value=True):
                    mode = run_async(detector.detect_proxy_mode(ProxyType.CLASH))
                    assert mode == ProxyMode.SYSTEM_PROXY

    def test_tun_detection_priority_over_fake_ip(self):
        """测试 TUN 模式优先于 Fake-IP"""
        detector = ProxyDetector()

        with patch.object(detector, '_is_system_proxy_enabled', return_value=False):
            with patch.object(detector, '_is_tun_mode_enabled', return_value=True):
                with patch.object(detector, '_is_fake_ip_enabled', return_value=True):
                    mode = run_async(detector.detect_proxy_mode(ProxyType.CLASH))
                    assert mode == ProxyMode.TUN

    def test_fake_ip_only_for_clash_types(self):
        """测试 Fake-IP 模式仅对 Clash 系列代理有效"""
        detector = ProxyDetector()

        clash_types = [ProxyType.CLASH, ProxyType.CLASH_VERGE, ProxyType.CLASH_META]
        non_clash_types = [ProxyType.V2RAY, ProxyType.SHADOWSOCKS, ProxyType.SURGE]

        with patch.object(detector, '_is_system_proxy_enabled', return_value=False):
            with patch.object(detector, '_is_tun_mode_enabled', return_value=False):
                with patch.object(detector, '_is_fake_ip_enabled', return_value=True):
                    # Clash 系列应该检测到 Fake-IP
                    for proxy_type in clash_types:
                        mode = run_async(detector.detect_proxy_mode(proxy_type))
                        assert mode == ProxyMode.FAKE_IP, \
                            f"{proxy_type} should detect FAKE_IP mode"

                    # 非 Clash 系列应该返回 RULE
                    for proxy_type in non_clash_types:
                        mode = run_async(detector.detect_proxy_mode(proxy_type))
                        assert mode == ProxyMode.RULE, \
                            f"{proxy_type} should return RULE mode, not FAKE_IP"

    def test_default_mode_is_rule(self):
        """测试默认模式为 RULE"""
        detector = ProxyDetector()

        with patch.object(detector, '_is_system_proxy_enabled', return_value=False):
            with patch.object(detector, '_is_tun_mode_enabled', return_value=False):
                with patch.object(detector, '_is_fake_ip_enabled', return_value=False):
                    for proxy_type in ProxyType:
                        mode = run_async(detector.detect_proxy_mode(proxy_type))
                        assert mode == ProxyMode.RULE, \
                            f"Default mode for {proxy_type} should be RULE"


# ============================================================================
# Additional Unit Tests
# ============================================================================

class TestProxyDetectorHelpers:
    """代理检测器辅助方法测试"""

    def test_is_clash_type(self):
        """测试 is_clash_type 方法"""
        detector = ProxyDetector()

        # Clash 系列
        assert detector.is_clash_type(ProxyType.CLASH) is True
        assert detector.is_clash_type(ProxyType.CLASH_VERGE) is True
        assert detector.is_clash_type(ProxyType.CLASH_META) is True

        # 非 Clash 系列
        assert detector.is_clash_type(ProxyType.V2RAY) is False
        assert detector.is_clash_type(ProxyType.SHADOWSOCKS) is False
        assert detector.is_clash_type(ProxyType.SURGE) is False
        assert detector.is_clash_type(ProxyType.NONE) is False
        assert detector.is_clash_type(ProxyType.OTHER) is False

    def test_cache_operations(self):
        """测试缓存操作"""
        detector = ProxyDetector()

        # 初始状态缓存为空
        assert detector.get_cached_info() is None

        # 设置缓存
        test_info = ProxyInfo(
            proxy_type=ProxyType.CLASH,
            proxy_mode=ProxyMode.SYSTEM_PROXY,
            process_name="clash.exe",
            process_pid=1234,
        )
        detector._cached_proxy_info = test_info

        # 获取缓存
        cached = detector.get_cached_info()
        assert cached is not None
        assert cached.proxy_type == ProxyType.CLASH
        assert cached.process_name == "clash.exe"

        # 清除缓存
        detector.clear_cache()
        assert detector.get_cached_info() is None

    def test_proxy_processes_mapping_complete(self):
        """测试代理进程映射完整性"""
        # 确保所有非 NONE 和 OTHER 的代理类型都有进程映射
        for proxy_type in ProxyType:
            if proxy_type not in (ProxyType.NONE, ProxyType.OTHER):
                assert proxy_type in ProxyDetector.PROXY_PROCESSES, \
                    f"Missing process mapping for {proxy_type}"
                assert len(ProxyDetector.PROXY_PROCESSES[proxy_type]) > 0, \
                    f"Empty process list for {proxy_type}"


class TestClashAPIDetection:
    """Clash API 检测测试"""

    def test_clash_config_paths_exist(self):
        """测试 Clash 配置路径列表非空"""
        assert len(ProxyDetector.CLASH_CONFIG_PATHS) > 0

    def test_clash_default_api_ports(self):
        """测试 Clash 默认 API 端口列表"""
        assert 9090 in ProxyDetector.CLASH_DEFAULT_API_PORTS
        assert len(ProxyDetector.CLASH_DEFAULT_API_PORTS) > 0

    def test_read_clash_config_no_yaml(self):
        """测试没有 PyYAML 时返回 None"""
        detector = ProxyDetector()

        with patch('src.core.channels.proxy_detector.HAS_YAML', False):
            result = detector._read_clash_config()
            assert result is None


class TestTUNModeDetection:
    """TUN 模式检测测试"""

    def test_tun_adapter_names(self):
        """测试 TUN 适配器名称检测"""
        detector = ProxyDetector()

        # 模拟有 TUN 适配器的网络接口
        mock_interfaces = {
            "clash-tun": [Mock()],
            "Ethernet": [Mock()],
        }

        with patch('src.core.channels.proxy_detector.psutil') as mock_psutil:
            mock_psutil.net_if_addrs.return_value = mock_interfaces

            result = detector._is_tun_mode_enabled()
            assert result is True

    def test_no_tun_adapter(self):
        """测试没有 TUN 适配器时返回 False"""
        detector = ProxyDetector()

        mock_interfaces = {
            "Ethernet": [Mock()],
            "Wi-Fi": [Mock()],
        }

        with patch('src.core.channels.proxy_detector.psutil') as mock_psutil:
            mock_psutil.net_if_addrs.return_value = mock_interfaces

            result = detector._is_tun_mode_enabled()
            assert result is False

    def test_tun_detection_no_psutil(self):
        """测试 psutil 不可用时返回 False"""
        detector = ProxyDetector()

        with patch('src.core.channels.proxy_detector.HAS_PSUTIL', False):
            result = detector._is_tun_mode_enabled()
            assert result is False


class TestFakeIPDetection:
    """Fake-IP 模式检测测试"""

    def test_fake_ip_from_config(self):
        """测试从配置文件检测 Fake-IP"""
        detector = ProxyDetector()

        mock_config = {
            "dns": {
                "enhanced-mode": "fake-ip"
            }
        }

        with patch.object(detector, '_read_clash_config', return_value=mock_config):
            result = detector._is_fake_ip_enabled()
            assert result is True

    def test_no_fake_ip_in_config(self):
        """测试配置文件中没有 Fake-IP"""
        detector = ProxyDetector()

        mock_config = {
            "dns": {
                "enhanced-mode": "redir-host"
            }
        }

        with patch.object(detector, '_read_clash_config', return_value=mock_config):
            with patch('src.core.channels.proxy_detector.socket') as mock_socket:
                mock_socket.gethostbyname.return_value = "142.250.185.78"  # 正常 IP
                result = detector._is_fake_ip_enabled()
                assert result is False

    def test_fake_ip_from_dns_resolution(self):
        """测试通过 DNS 解析检测 Fake-IP"""
        detector = ProxyDetector()

        with patch.object(detector, '_read_clash_config', return_value=None):
            with patch('src.core.channels.proxy_detector.socket') as mock_socket:
                # Fake-IP 返回 198.18.x.x 段
                mock_socket.gethostbyname.return_value = "198.18.0.1"
                result = detector._is_fake_ip_enabled()
                assert result is True


class TestAsyncDetection:
    """异步检测测试"""

    def test_detect_returns_proxy_info(self):
        """测试 detect 方法返回 ProxyInfo"""
        detector = ProxyDetector()

        mock_proc = Mock()
        mock_proc.info = {'pid': 1234, 'name': 'clash.exe'}

        with patch('src.core.channels.proxy_detector.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = [mock_proc]

            with patch.object(detector, '_is_system_proxy_enabled', return_value=True):
                with patch.object(detector, '_is_tun_mode_enabled', return_value=False):
                    with patch.object(detector, '_is_fake_ip_enabled', return_value=False):
                        with patch.object(detector, 'get_clash_api_info', return_value=("127.0.0.1:9090", "")):
                            result = run_async(detector.detect())

                            assert isinstance(result, ProxyInfo)
                            assert result.proxy_type == ProxyType.CLASH
                            assert result.proxy_mode == ProxyMode.SYSTEM_PROXY
                            assert result.process_name == "clash.exe"
                            assert result.process_pid == 1234

    def test_detect_no_proxy(self):
        """测试没有代理时返回 NONE"""
        detector = ProxyDetector()

        with patch('src.core.channels.proxy_detector.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = []

            result = run_async(detector.detect())

            assert isinstance(result, ProxyInfo)
            assert result.proxy_type == ProxyType.NONE
            assert result.proxy_mode == ProxyMode.NONE


class TestSystemProxyPACDetection:
    def test_is_system_proxy_enabled_detects_pac_url(self):
        detector = ProxyDetector()

        with patch('src.core.channels.proxy_detector.winreg') as mock_winreg:
            mock_key = MagicMock()
            mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key

            def query_value(_, name):
                values = {
                    "ProxyEnable": (0, None),
                    "AutoConfigURL": ("http://127.0.0.1:33331/commands/pac", None),
                    "AutoDetect": (0, None),
                }
                if name not in values:
                    raise FileNotFoundError(name)
                return values[name]

            mock_winreg.QueryValueEx.side_effect = query_value

            assert detector._is_system_proxy_enabled() is True

    def test_detect_no_psutil(self):
        """测试 psutil 不可用时返回 NONE"""
        detector = ProxyDetector()

        with patch('src.core.channels.proxy_detector.HAS_PSUTIL', False):
            result = run_async(detector.detect())

            assert isinstance(result, ProxyInfo)
            assert result.proxy_type == ProxyType.NONE
            assert result.proxy_mode == ProxyMode.NONE
