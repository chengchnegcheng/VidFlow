"""
微信进程管理器属性测试

Property 10: WeChat Process Port Caching
Validates: Requirements 8.1, 8.2, 8.6
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import Mock, patch, MagicMock
from typing import List, Set, Dict
from datetime import datetime
import threading
import time

from src.core.channels.wechat_process_manager import WeChatProcessManager
from src.core.channels.models import WeChatProcess


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def port_strategy(draw):
    """生成有效端口号"""
    return draw(st.integers(min_value=1024, max_value=65535))


@st.composite
def port_set_strategy(draw):
    """生成端口集合"""
    num_ports = draw(st.integers(min_value=0, max_value=5))
    return set(draw(st.integers(min_value=1024, max_value=65535)) for _ in range(num_ports))


@st.composite
def wechat_process_strategy(draw):
    """生成微信进程信息"""
    pid = draw(st.integers(min_value=1000, max_value=65535))
    name = draw(st.sampled_from(WeChatProcessManager.WECHAT_PROCESSES))
    ports = draw(port_set_strategy())
    return {
        "pid": pid,
        "name": name,
        "exe_path": f"C:\\Program Files\\WeChat\\{name}",
        "ports": ports,
    }


@st.composite
def process_list_strategy(draw):
    """生成进程列表"""
    num_processes = draw(st.integers(min_value=0, max_value=3))
    processes = []
    used_pids = set()
    
    for i in range(num_processes):
        pid = 1000 + i * 100 + draw(st.integers(min_value=0, max_value=99))
        while pid in used_pids:
            pid += 1
        used_pids.add(pid)
        
        name = draw(st.sampled_from(WeChatProcessManager.WECHAT_PROCESSES))
        ports = draw(port_set_strategy())
        
        processes.append({
            "pid": pid,
            "name": name,
            "exe_path": f"C:\\Program Files\\WeChat\\{name}",
            "ports": ports,
        })
    
    return processes


# ============================================================================
# Property 10: WeChat Process Port Caching
# Validates: Requirements 8.1, 8.2, 8.6
# ============================================================================

class TestWeChatProcessPortCaching:
    """
    Property 10: WeChat Process Port Caching
    
    For any WeChat process, the WeChatProcessManager should maintain an accurate
    mapping of ports to process IDs. After a cache refresh, is_wechat_port()
    should return true for all ports currently used by WeChat processes.
    
    **Feature: weixin-channels-deep-research, Property 10: WeChat Process Port Caching**
    **Validates: Requirements 8.1, 8.2, 8.6**
    """

    @given(processes=process_list_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_port_cache_accuracy(self, processes):
        """测试端口缓存准确性
        
        Property: 刷新后，is_wechat_port() 应该对所有微信进程使用的端口返回True。
        """
        manager = WeChatProcessManager()
        
        # 收集所有端口
        all_ports = set()
        for proc in processes:
            all_ports.update(proc["ports"])
        
        # 模拟进程迭代器
        mock_processes = []
        for proc in processes:
            mock_proc = Mock()
            mock_proc.info = {
                'pid': proc["pid"],
                'name': proc["name"],
                'exe': proc["exe_path"],
            }
            
            # 模拟网络连接
            mock_connections = []
            for port in proc["ports"]:
                mock_conn = Mock()
                mock_conn.laddr = Mock()
                mock_conn.laddr.port = port
                mock_connections.append(mock_conn)
            
            mock_proc.net_connections.return_value = mock_connections
            mock_processes.append(mock_proc)
        
        with patch('src.core.channels.wechat_process_manager.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = mock_processes
            
            manager.refresh_cache()
            
            # 验证所有端口都被正确缓存
            for port in all_ports:
                assert manager.is_wechat_port(port) is True, \
                    f"Port {port} should be cached as WeChat port"

    @given(processes=process_list_strategy(), random_port=port_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_non_wechat_port_not_cached(self, processes, random_port):
        """测试非微信端口不被缓存
        
        Property: 不属于微信进程的端口应该返回False。
        """
        manager = WeChatProcessManager()
        
        # 收集所有微信端口
        wechat_ports = set()
        for proc in processes:
            wechat_ports.update(proc["ports"])
        
        # 确保随机端口不在微信端口中
        assume(random_port not in wechat_ports)
        
        # 模拟进程迭代器
        mock_processes = []
        for proc in processes:
            mock_proc = Mock()
            mock_proc.info = {
                'pid': proc["pid"],
                'name': proc["name"],
                'exe': proc["exe_path"],
            }
            
            mock_connections = []
            for port in proc["ports"]:
                mock_conn = Mock()
                mock_conn.laddr = Mock()
                mock_conn.laddr.port = port
                mock_connections.append(mock_conn)
            
            mock_proc.net_connections.return_value = mock_connections
            mock_processes.append(mock_proc)
        
        with patch('src.core.channels.wechat_process_manager.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = mock_processes
            
            manager.refresh_cache()
            
            # 验证随机端口不被缓存
            assert manager.is_wechat_port(random_port) is False, \
                f"Port {random_port} should not be cached as WeChat port"

    @given(processes=process_list_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_process_count_accuracy(self, processes):
        """测试进程计数准确性
        
        Property: 刷新后，进程计数应该等于实际微信进程数量。
        """
        manager = WeChatProcessManager()
        
        mock_processes = []
        for proc in processes:
            mock_proc = Mock()
            mock_proc.info = {
                'pid': proc["pid"],
                'name': proc["name"],
                'exe': proc["exe_path"],
            }
            mock_proc.net_connections.return_value = []
            mock_processes.append(mock_proc)
        
        with patch('src.core.channels.wechat_process_manager.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = mock_processes
            
            manager.refresh_cache()
            
            assert manager.get_process_count() == len(processes), \
                f"Process count should be {len(processes)}"


# ============================================================================
# Additional Unit Tests
# ============================================================================

class TestWeChatProcessManagerBasics:
    """微信进程管理器基础测试"""

    def test_default_wechat_processes(self):
        """测试默认微信进程列表"""
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
            assert proc in WeChatProcessManager.WECHAT_PROCESSES

    def test_default_refresh_interval(self):
        """测试默认刷新间隔"""
        manager = WeChatProcessManager()
        assert manager.refresh_interval == 2.0

    def test_custom_refresh_interval(self):
        """测试自定义刷新间隔"""
        manager = WeChatProcessManager(refresh_interval=5.0)
        assert manager.refresh_interval == 5.0

    def test_set_refresh_interval(self):
        """测试设置刷新间隔"""
        manager = WeChatProcessManager()
        manager.refresh_interval = 10.0
        assert manager.refresh_interval == 10.0
        
        # 负值不应该被接受
        manager.refresh_interval = -1.0
        assert manager.refresh_interval == 10.0

    def test_initial_state(self):
        """测试初始状态"""
        manager = WeChatProcessManager()
        
        assert manager.is_monitoring is False
        assert manager.get_process_count() == 0
        assert manager.get_port_count() == 0
        assert manager.is_wechat_running() is False
        assert manager.get_last_refresh_time() is None


class TestProcessDetection:
    """进程检测测试"""

    def test_is_wechat_process_case_insensitive(self):
        """测试进程检测不区分大小写"""
        manager = WeChatProcessManager()
        
        assert manager._is_wechat_process("WeChat.exe") is True
        assert manager._is_wechat_process("wechat.exe") is True
        assert manager._is_wechat_process("WECHAT.EXE") is True

    def test_is_wechat_process_unknown(self):
        """测试未知进程返回False"""
        manager = WeChatProcessManager()
        
        assert manager._is_wechat_process("chrome.exe") is False
        assert manager._is_wechat_process("notepad.exe") is False
        assert manager._is_wechat_process("python.exe") is False

    def test_is_wechat_process_empty(self):
        """测试空进程名返回False"""
        manager = WeChatProcessManager()
        
        assert manager._is_wechat_process("") is False
        assert manager._is_wechat_process(None) is False


class TestCacheOperations:
    """缓存操作测试"""

    def test_clear_cache(self):
        """测试清除缓存"""
        manager = WeChatProcessManager()
        
        # 手动添加一些数据
        manager._processes[1234] = WeChatProcess(
            pid=1234, name="WeChat.exe", exe_path="", ports={8080}
        )
        manager._port_cache[8080] = 1234
        manager._known_pids.add(1234)
        manager._last_refresh = datetime.now()
        
        manager.clear_cache()
        
        assert manager.get_process_count() == 0
        assert manager.get_port_count() == 0
        assert manager.get_last_refresh_time() is None

    def test_get_all_ports(self):
        """测试获取所有端口"""
        manager = WeChatProcessManager()
        
        manager._port_cache = {8080: 1234, 8081: 1234, 9090: 5678}
        
        ports = manager.get_all_ports()
        assert ports == {8080, 8081, 9090}

    def test_get_process_by_port(self):
        """测试根据端口获取进程"""
        manager = WeChatProcessManager()
        
        proc = WeChatProcess(pid=1234, name="WeChat.exe", exe_path="", ports={8080})
        manager._processes[1234] = proc
        manager._port_cache[8080] = 1234
        
        result = manager.get_process_by_port(8080)
        assert result is not None
        assert result.pid == 1234
        
        # 不存在的端口
        assert manager.get_process_by_port(9999) is None

    def test_get_process_by_pid(self):
        """测试根据PID获取进程"""
        manager = WeChatProcessManager()
        
        proc = WeChatProcess(pid=1234, name="WeChat.exe", exe_path="", ports={8080})
        manager._processes[1234] = proc
        
        result = manager.get_process_by_pid(1234)
        assert result is not None
        assert result.name == "WeChat.exe"
        
        # 不存在的PID
        assert manager.get_process_by_pid(9999) is None


class TestMonitoring:
    """监控测试"""

    def test_start_monitoring_when_already_running(self):
        """测试已运行时启动监控"""
        manager = WeChatProcessManager()
        manager._is_monitoring = True
        
        # 不应该抛出异常
        manager.start_monitoring()

    def test_stop_monitoring_when_not_running(self):
        """测试未运行时停止监控"""
        manager = WeChatProcessManager()
        
        # 不应该抛出异常
        manager.stop_monitoring()

    def test_start_and_stop_monitoring(self):
        """测试启动和停止监控"""
        manager = WeChatProcessManager(refresh_interval=0.1)
        
        with patch('src.core.channels.wechat_process_manager.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = []
            
            manager.start_monitoring()
            assert manager.is_monitoring is True
            
            # 等待一小段时间
            time.sleep(0.2)
            
            manager.stop_monitoring()
            assert manager.is_monitoring is False


class TestRestartDetection:
    """重启检测测试"""

    def test_add_restart_callback(self):
        """测试添加重启回调"""
        manager = WeChatProcessManager()
        
        callback_data = []
        def callback(stopped, started):
            callback_data.append((stopped, started))
        
        manager.add_restart_callback(callback)
        assert len(manager._restart_callbacks) == 1

    def test_remove_restart_callback(self):
        """测试移除重启回调"""
        manager = WeChatProcessManager()
        
        def callback(stopped, started):
            pass
        
        manager.add_restart_callback(callback)
        manager.remove_restart_callback(callback)
        assert len(manager._restart_callbacks) == 0

    def test_restart_detection(self):
        """测试重启检测"""
        manager = WeChatProcessManager()
        
        callback_data = []
        def callback(stopped, started):
            callback_data.append((stopped, started))
        
        manager.add_restart_callback(callback)
        
        # 设置已知PID
        manager._known_pids = {1234}
        
        # 模拟重启：旧进程退出，新进程启动
        manager._detect_restart({1234}, {5678})
        
        assert len(callback_data) == 1
        stopped, started = callback_data[0]
        assert 1234 in stopped
        assert 5678 in started


class TestRefreshCache:
    """刷新缓存测试"""

    def test_refresh_cache_no_psutil(self):
        """测试psutil不可用时刷新缓存"""
        manager = WeChatProcessManager()
        
        with patch('src.core.channels.wechat_process_manager.HAS_PSUTIL', False):
            manager.refresh_cache()
            # 不应该抛出异常
            assert manager.get_process_count() == 0

    def test_refresh_cache_with_processes(self):
        """测试有进程时刷新缓存"""
        manager = WeChatProcessManager()
        
        mock_proc = Mock()
        mock_proc.info = {
            'pid': 1234,
            'name': 'WeChat.exe',
            'exe': 'C:\\WeChat\\WeChat.exe',
        }
        
        mock_conn = Mock()
        mock_conn.laddr = Mock()
        mock_conn.laddr.port = 8080
        mock_proc.net_connections.return_value = [mock_conn]
        
        with patch('src.core.channels.wechat_process_manager.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = [mock_proc]
            
            manager.refresh_cache()
            
            assert manager.get_process_count() == 1
            assert manager.is_wechat_port(8080) is True
            assert manager.get_last_refresh_time() is not None

    def test_refresh_cache_updates_existing_process(self):
        """测试刷新缓存更新现有进程"""
        manager = WeChatProcessManager()
        
        # 添加现有进程
        old_proc = WeChatProcess(
            pid=1234, name="WeChat.exe", exe_path="", ports={8080}
        )
        manager._processes[1234] = old_proc
        
        # 模拟刷新，端口变化
        mock_proc = Mock()
        mock_proc.info = {
            'pid': 1234,
            'name': 'WeChat.exe',
            'exe': 'C:\\WeChat\\WeChat.exe',
        }
        
        mock_conn = Mock()
        mock_conn.laddr = Mock()
        mock_conn.laddr.port = 9090  # 新端口
        mock_proc.net_connections.return_value = [mock_conn]
        
        with patch('src.core.channels.wechat_process_manager.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = [mock_proc]
            
            manager.refresh_cache()
            
            # 端口应该更新
            assert manager.is_wechat_port(9090) is True
            assert manager.is_wechat_port(8080) is False


class TestThreadSafety:
    """线程安全测试"""

    def test_concurrent_access(self):
        """测试并发访问"""
        manager = WeChatProcessManager()
        
        # 添加一些数据
        manager._processes[1234] = WeChatProcess(
            pid=1234, name="WeChat.exe", exe_path="", ports={8080}
        )
        manager._port_cache[8080] = 1234
        
        results = []
        errors = []
        
        def reader():
            try:
                for _ in range(100):
                    manager.is_wechat_port(8080)
                    manager.get_process_count()
                    manager.get_all_ports()
                results.append(True)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) == 5
