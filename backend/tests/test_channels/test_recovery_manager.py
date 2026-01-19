"""
恢复管理器属性测试

Property 11: Error Recovery with Exponential Backoff
Property 12: Video Preservation During Recovery
Validates: Requirements 9.1, 9.2, 9.4, 9.5, 9.6
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, patch, AsyncMock
from typing import List
from datetime import datetime
import asyncio
import time

from src.core.channels.recovery_manager import RecoveryManager, ComponentInfo
from src.core.channels.models import RecoveryAttempt


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
def attempt_number_strategy(draw):
    """生成尝试次数"""
    return draw(st.integers(min_value=1, max_value=10))


@st.composite
def backoff_config_strategy(draw):
    """生成退避配置"""
    base = draw(st.floats(min_value=0.1, max_value=5.0))
    max_val = draw(st.floats(min_value=base, max_value=60.0))
    return {"base": base, "max": max_val}


@st.composite
def video_list_strategy(draw):
    """生成视频列表"""
    num_videos = draw(st.integers(min_value=0, max_value=20))
    return [{"id": f"video_{i}", "url": f"https://example.com/{i}.mp4"} for i in range(num_videos)]


# ============================================================================
# Property 11: Error Recovery with Exponential Backoff
# Validates: Requirements 9.1, 9.2, 9.4, 9.5
# ============================================================================

class TestExponentialBackoff:
    """
    Property 11: Error Recovery with Exponential Backoff
    
    For any component failure, the RecoveryManager should attempt recovery with
    exponential backoff delays. The delay should double with each attempt
    (up to BACKOFF_MAX), and recovery should stop after MAX_RETRIES failures.
    
    **Feature: weixin-channels-deep-research, Property 11: Error Recovery with Exponential Backoff**
    **Validates: Requirements 9.1, 9.2, 9.4, 9.5**
    """

    @given(attempt=attempt_number_strategy(), config=backoff_config_strategy())
    @settings(max_examples=100)
    def test_backoff_delay_doubles(self, attempt, config):
        """测试退避延迟翻倍
        
        Property: 延迟应该随着尝试次数指数增长。
        """
        manager = RecoveryManager(
            backoff_base=config["base"],
            backoff_max=config["max"],
        )
        
        delay = manager.get_backoff_delay(attempt)
        expected = min(config["base"] * (2 ** (attempt - 1)), config["max"])
        
        assert abs(delay - expected) < 0.001, \
            f"Expected delay {expected}, got {delay} for attempt {attempt}"

    @given(attempt=attempt_number_strategy(), config=backoff_config_strategy())
    @settings(max_examples=100)
    def test_backoff_delay_capped(self, attempt, config):
        """测试退避延迟上限
        
        Property: 延迟不应超过最大值。
        """
        manager = RecoveryManager(
            backoff_base=config["base"],
            backoff_max=config["max"],
        )
        
        delay = manager.get_backoff_delay(attempt)
        assert delay <= config["max"], \
            f"Delay {delay} exceeds max {config['max']}"

    def test_backoff_delay_sequence(self):
        """测试退避延迟序列"""
        manager = RecoveryManager(backoff_base=1.0, backoff_max=30.0)
        
        expected_delays = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
        
        for i, expected in enumerate(expected_delays, start=1):
            delay = manager.get_backoff_delay(i)
            assert delay == expected, \
                f"Attempt {i}: expected {expected}, got {delay}"

    def test_backoff_delay_zero_attempt(self):
        """测试零次尝试返回零延迟"""
        manager = RecoveryManager()
        assert manager.get_backoff_delay(0) == 0.0
        assert manager.get_backoff_delay(-1) == 0.0

    def test_max_retries_exceeded(self):
        """测试超过最大重试次数"""
        manager = RecoveryManager(max_retries=3)
        
        # 注册组件
        component = Mock()
        manager.register_component("test", component)
        
        # 模拟多次失败
        manager._components["test"].attempt_count = 3
        
        # 第4次尝试应该失败
        result = run_async(manager.attempt_recovery("test", Exception("test error")))
        assert result is False

    def test_recovery_stops_after_max_retries(self):
        """测试达到最大重试次数后停止"""
        manager = RecoveryManager(max_retries=2, backoff_base=0.01)
        
        component = Mock()
        recovery_func = AsyncMock(return_value=False)
        manager.register_component("test", component, recovery_func=recovery_func)
        
        # 第一次尝试
        run_async(manager.attempt_recovery("test", Exception("error1")))
        # 第二次尝试
        run_async(manager.attempt_recovery("test", Exception("error2")))
        # 第三次尝试应该直接失败
        result = run_async(manager.attempt_recovery("test", Exception("error3")))
        
        assert result is False
        # 恢复函数只应该被调用2次
        assert recovery_func.call_count == 2


# ============================================================================
# Property 12: Video Preservation During Recovery
# Validates: Requirements 9.6, 2.6
# ============================================================================

class TestVideoPreservation:
    """
    Property 12: Video Preservation During Recovery
    
    For any recovery attempt (successful or failed), the list of detected videos
    should remain unchanged. No videos should be lost during error recovery or
    mode switching.
    
    **Feature: weixin-channels-deep-research, Property 12: Video Preservation During Recovery**
    **Validates: Requirements 9.6, 2.6**
    """

    @given(videos=video_list_strategy())
    @settings(max_examples=100, deadline=None)
    def test_videos_preserved_during_recovery(self, videos):
        """测试恢复期间视频被保留
        
        Property: 恢复期间已检测的视频应该保持不变。
        """
        manager = RecoveryManager(backoff_base=0.01)
        
        # 保留视频
        manager.preserve_videos(videos)
        
        # 模拟恢复
        component = Mock()
        manager.register_component("test", component)
        run_async(manager.attempt_recovery("test", Exception("test error")))
        
        # 验证视频仍然存在
        preserved = manager.get_preserved_videos()
        assert len(preserved) == len(videos), \
            f"Expected {len(videos)} videos, got {len(preserved)}"
        
        for i, video in enumerate(videos):
            assert preserved[i] == video, \
                f"Video {i} was modified during recovery"

    @given(videos=video_list_strategy())
    @settings(max_examples=100)
    def test_videos_preserved_after_failed_recovery(self, videos):
        """测试失败恢复后视频被保留
        
        Property: 即使恢复失败，视频也应该保持不变。
        """
        manager = RecoveryManager(max_retries=1, backoff_base=0.01)
        
        # 保留视频
        manager.preserve_videos(videos)
        
        # 模拟失败的恢复
        component = Mock()
        recovery_func = AsyncMock(return_value=False)
        manager.register_component("test", component, recovery_func=recovery_func)
        
        # 多次失败
        run_async(manager.attempt_recovery("test", Exception("error1")))
        run_async(manager.attempt_recovery("test", Exception("error2")))
        
        # 验证视频仍然存在
        preserved = manager.get_preserved_videos()
        assert len(preserved) == len(videos)

    def test_preserve_videos_creates_copy(self):
        """测试保留视频创建副本"""
        manager = RecoveryManager()
        
        videos = [{"id": "1"}, {"id": "2"}]
        manager.preserve_videos(videos)
        
        # 修改原始列表
        videos.append({"id": "3"})
        
        # 保留的视频不应该受影响
        preserved = manager.get_preserved_videos()
        assert len(preserved) == 2

    def test_get_preserved_videos_returns_copy(self):
        """测试获取保留视频返回副本"""
        manager = RecoveryManager()
        
        videos = [{"id": "1"}, {"id": "2"}]
        manager.preserve_videos(videos)
        
        # 修改返回的列表
        preserved = manager.get_preserved_videos()
        preserved.append({"id": "3"})
        
        # 内部列表不应该受影响
        assert len(manager.get_preserved_videos()) == 2

    def test_clear_preserved_videos(self):
        """测试清除保留视频"""
        manager = RecoveryManager()
        
        videos = [{"id": "1"}, {"id": "2"}]
        manager.preserve_videos(videos)
        
        manager.clear_preserved_videos()
        
        assert len(manager.get_preserved_videos()) == 0


# ============================================================================
# Additional Unit Tests
# ============================================================================

class TestRecoveryManagerBasics:
    """恢复管理器基础测试"""

    def test_default_config(self):
        """测试默认配置"""
        manager = RecoveryManager()
        
        assert manager.max_retries == 3
        assert manager.backoff_base == 1.0
        assert manager.backoff_max == 30.0
        assert manager.watchdog_interval == 5.0

    def test_custom_config(self):
        """测试自定义配置"""
        manager = RecoveryManager(
            max_retries=5,
            backoff_base=2.0,
            backoff_max=60.0,
            watchdog_interval=10.0,
        )
        
        assert manager.max_retries == 5
        assert manager.backoff_base == 2.0
        assert manager.backoff_max == 60.0
        assert manager.watchdog_interval == 10.0


class TestComponentRegistration:
    """组件注册测试"""

    def test_register_component(self):
        """测试注册组件"""
        manager = RecoveryManager()
        component = Mock()
        
        manager.register_component("test", component)
        
        assert "test" in manager._components
        assert manager._components["test"].component == component

    def test_unregister_component(self):
        """测试取消注册组件"""
        manager = RecoveryManager()
        component = Mock()
        
        manager.register_component("test", component)
        manager.unregister_component("test")
        
        assert "test" not in manager._components

    def test_register_with_health_check(self):
        """测试注册带健康检查的组件"""
        manager = RecoveryManager()
        component = Mock()
        health_check = Mock(return_value=True)
        
        manager.register_component("test", component, health_check=health_check)
        
        assert manager._components["test"].health_check == health_check

    def test_register_with_recovery_func(self):
        """测试注册带恢复函数的组件"""
        manager = RecoveryManager()
        component = Mock()
        recovery_func = AsyncMock(return_value=True)
        
        manager.register_component("test", component, recovery_func=recovery_func)
        
        assert manager._components["test"].recovery_func == recovery_func


class TestRecoveryAttempts:
    """恢复尝试测试"""

    def test_reset_attempts(self):
        """测试重置尝试计数"""
        manager = RecoveryManager()
        component = Mock()
        
        manager.register_component("test", component)
        manager._components["test"].attempt_count = 5
        manager._components["test"].last_error = "some error"
        
        manager.reset_attempts("test")
        
        assert manager._components["test"].attempt_count == 0
        assert manager._components["test"].last_error is None

    def test_reset_all_attempts(self):
        """测试重置所有尝试计数"""
        manager = RecoveryManager()
        
        manager.register_component("test1", Mock())
        manager.register_component("test2", Mock())
        
        manager._components["test1"].attempt_count = 3
        manager._components["test2"].attempt_count = 5
        
        manager.reset_all_attempts()
        
        assert manager._components["test1"].attempt_count == 0
        assert manager._components["test2"].attempt_count == 0

    def test_get_recovery_history(self):
        """测试获取恢复历史"""
        manager = RecoveryManager(backoff_base=0.01)
        component = Mock()
        recovery_func = AsyncMock(return_value=True)
        
        manager.register_component("test", component, recovery_func=recovery_func)
        run_async(manager.attempt_recovery("test", Exception("error")))
        
        history = manager.get_recovery_history()
        assert len(history) == 1
        assert history[0].component == "test"
        assert history[0].success is True


class TestComponentStatus:
    """组件状态测试"""

    def test_get_component_status(self):
        """测试获取组件状态"""
        manager = RecoveryManager()
        component = Mock()
        
        manager.register_component("test", component)
        
        status = manager.get_component_status("test")
        assert status is not None
        assert status["name"] == "test"
        assert status["is_healthy"] is True
        assert status["attempt_count"] == 0

    def test_get_component_status_unknown(self):
        """测试获取未知组件状态"""
        manager = RecoveryManager()
        
        status = manager.get_component_status("unknown")
        assert status is None

    def test_get_all_component_status(self):
        """测试获取所有组件状态"""
        manager = RecoveryManager()
        
        manager.register_component("test1", Mock())
        manager.register_component("test2", Mock())
        
        status = manager.get_all_component_status()
        assert "test1" in status
        assert "test2" in status


class TestWatchdog:
    """看门狗测试"""

    def test_start_watchdog(self):
        """测试启动看门狗"""
        manager = RecoveryManager(watchdog_interval=0.1)
        
        manager.start_watchdog()
        assert manager.is_watchdog_running is True
        
        manager.stop_watchdog()
        assert manager.is_watchdog_running is False

    def test_start_watchdog_when_already_running(self):
        """测试已运行时启动看门狗"""
        manager = RecoveryManager(watchdog_interval=0.1)
        
        manager.start_watchdog()
        manager.start_watchdog()  # 不应该抛出异常
        
        manager.stop_watchdog()

    def test_stop_watchdog_when_not_running(self):
        """测试未运行时停止看门狗"""
        manager = RecoveryManager()
        
        manager.stop_watchdog()  # 不应该抛出异常

    def test_watchdog_checks_health(self):
        """测试看门狗检查健康状态"""
        manager = RecoveryManager(watchdog_interval=0.1)
        
        health_check = Mock(return_value=False)
        manager.register_component("test", Mock(), health_check=health_check)
        
        manager.start_watchdog()
        time.sleep(0.3)  # 等待几次检查
        manager.stop_watchdog()
        
        assert health_check.called
        assert manager._components["test"].is_healthy is False


class TestRecoveryExecution:
    """恢复执行测试"""

    def test_successful_recovery(self):
        """测试成功恢复"""
        manager = RecoveryManager(backoff_base=0.01)
        
        component = Mock()
        recovery_func = AsyncMock(return_value=True)
        manager.register_component("test", component, recovery_func=recovery_func)
        
        result = run_async(manager.attempt_recovery("test", Exception("error")))
        
        assert result is True
        assert manager._components["test"].is_healthy is True
        assert recovery_func.called

    def test_failed_recovery(self):
        """测试失败恢复"""
        manager = RecoveryManager(backoff_base=0.01)
        
        component = Mock()
        recovery_func = AsyncMock(return_value=False)
        manager.register_component("test", component, recovery_func=recovery_func)
        
        result = run_async(manager.attempt_recovery("test", Exception("error")))
        
        assert result is False
        assert manager._components["test"].is_healthy is False

    def test_recovery_unknown_component(self):
        """测试恢复未知组件"""
        manager = RecoveryManager()
        
        result = run_async(manager.attempt_recovery("unknown", Exception("error")))
        
        assert result is False

    def test_default_recovery_with_restart(self):
        """测试默认恢复（restart方法）"""
        manager = RecoveryManager(backoff_base=0.01)
        
        component = Mock()
        component.restart = Mock()
        manager.register_component("test", component)
        
        result = run_async(manager.attempt_recovery("test", Exception("error")))
        
        assert result is True
        assert component.restart.called

    def test_default_recovery_with_stop_start(self):
        """测试默认恢复（stop+start方法）"""
        manager = RecoveryManager(backoff_base=0.01)
        
        component = Mock(spec=['stop', 'start'])  # 只有stop和start，没有restart
        component.stop = Mock()
        component.start = Mock()
        manager.register_component("test", component)
        
        result = run_async(manager.attempt_recovery("test", Exception("error")))
        
        assert result is True
        assert component.stop.called
        assert component.start.called


class TestErrorsRecoveredCount:
    """恢复错误计数测试"""

    def test_get_errors_recovered_count(self):
        """测试获取成功恢复的错误数量"""
        manager = RecoveryManager(backoff_base=0.01)
        
        component = Mock()
        recovery_func = AsyncMock(return_value=True)
        manager.register_component("test", component, recovery_func=recovery_func)
        
        assert manager.get_errors_recovered_count() == 0
        
        run_async(manager.attempt_recovery("test", Exception("error1")))
        assert manager.get_errors_recovered_count() == 1
        
        manager.reset_attempts("test")
        run_async(manager.attempt_recovery("test", Exception("error2")))
        assert manager.get_errors_recovered_count() == 2
