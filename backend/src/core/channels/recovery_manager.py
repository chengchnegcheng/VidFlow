"""
恢复管理器

管理错误恢复和自愈。
支持组件注册、指数退避重试、看门狗监控和恢复历史记录。

Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5
"""

import logging
import asyncio
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field

from .models import RecoveryAttempt

logger = logging.getLogger(__name__)


@dataclass
class ComponentInfo:
    """组件信息"""
    name: str
    component: Any
    health_check: Optional[Callable[[], bool]] = None
    recovery_func: Optional[Callable[[], Awaitable[bool]]] = None
    attempt_count: int = 0
    last_error: Optional[str] = None
    last_recovery_at: Optional[datetime] = None
    is_healthy: bool = True


class RecoveryManager:
    """错误恢复管理器

    管理组件的错误恢复和自愈。

    Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5
    """

    # 默认配置
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF_BASE = 1.0  # 秒
    DEFAULT_BACKOFF_MAX = 30.0  # 秒
    DEFAULT_WATCHDOG_INTERVAL = 5.0  # 秒

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        backoff_max: float = DEFAULT_BACKOFF_MAX,
        watchdog_interval: float = DEFAULT_WATCHDOG_INTERVAL,
    ):
        """初始化恢复管理器

        Args:
            max_retries: 最大重试次数
            backoff_base: 退避基数（秒）
            backoff_max: 退避最大值（秒）
            watchdog_interval: 看门狗检查间隔（秒）
        """
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.watchdog_interval = watchdog_interval

        # 组件注册表
        self._components: Dict[str, ComponentInfo] = {}

        # 恢复历史
        self._attempts: List[RecoveryAttempt] = []

        # 看门狗
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_stop_event = threading.Event()
        self._is_watchdog_running = False

        # 锁
        self._lock = threading.RLock()

        # 视频保留（恢复期间不丢失）
        self._preserved_videos: List[Any] = []

    def register_component(
        self,
        name: str,
        component: Any,
        health_check: Optional[Callable[[], bool]] = None,
        recovery_func: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> None:
        """注册需要监控的组件

        Args:
            name: 组件名称
            component: 组件实例
            health_check: 健康检查函数
            recovery_func: 恢复函数
        """
        with self._lock:
            self._components[name] = ComponentInfo(
                name=name,
                component=component,
                health_check=health_check,
                recovery_func=recovery_func,
            )
            logger.info(f"Registered component: {name}")

    def unregister_component(self, name: str) -> None:
        """取消注册组件

        Args:
            name: 组件名称
        """
        with self._lock:
            if name in self._components:
                del self._components[name]
                logger.info(f"Unregistered component: {name}")

    def get_backoff_delay(self, attempt: int) -> float:
        """计算指数退避延迟

        Property 11: Error Recovery with Exponential Backoff
        延迟应该随着尝试次数指数增长，但不超过最大值。

        Args:
            attempt: 尝试次数（从1开始）

        Returns:
            延迟时间（秒）
        """
        if attempt <= 0:
            return 0.0

        # 指数退避: base * 2^(attempt-1)
        delay = self.backoff_base * (2 ** (attempt - 1))

        # 限制最大值
        return min(delay, self.backoff_max)

    async def attempt_recovery(
        self,
        component_name: str,
        error: Exception,
    ) -> bool:
        """尝试恢复组件

        Property 11: Error Recovery with Exponential Backoff
        使用指数退避延迟进行重试，最多重试max_retries次。

        Property 12: Video Preservation During Recovery
        恢复期间保留已检测的视频。

        Args:
            component_name: 组件名称
            error: 错误异常

        Returns:
            是否恢复成功
        """
        with self._lock:
            if component_name not in self._components:
                logger.error(f"Unknown component: {component_name}")
                return False

            component_info = self._components[component_name]
            component_info.attempt_count += 1
            component_info.last_error = str(error)
            component_info.is_healthy = False

            attempt_number = component_info.attempt_count

        # 检查是否超过最大重试次数
        if attempt_number > self.max_retries:
            logger.error(f"Max retries exceeded for {component_name}")
            self._record_attempt(component_name, str(error), attempt_number, False, 0.0)
            return False

        # 计算退避延迟
        delay = self.get_backoff_delay(attempt_number)

        logger.info(f"Attempting recovery for {component_name} "
                   f"(attempt {attempt_number}/{self.max_retries}, delay={delay}s)")

        # 等待退避延迟
        if delay > 0:
            await asyncio.sleep(delay)

        # 尝试恢复
        success = False
        try:
            if component_info.recovery_func:
                success = await component_info.recovery_func()
            else:
                # 默认恢复：尝试重启组件
                success = await self._default_recovery(component_info)

            if success:
                with self._lock:
                    component_info.is_healthy = True
                    component_info.last_recovery_at = datetime.now()
                logger.info(f"Recovery successful for {component_name}")
            else:
                logger.warning(f"Recovery failed for {component_name}")

        except Exception as e:
            logger.error(f"Recovery error for {component_name}: {e}")
            success = False

        # 记录尝试
        self._record_attempt(component_name, str(error), attempt_number, success, delay)

        return success

    async def _default_recovery(self, component_info: ComponentInfo) -> bool:
        """默认恢复逻辑

        Args:
            component_info: 组件信息

        Returns:
            是否恢复成功
        """
        component = component_info.component

        # 尝试调用组件的restart方法
        if hasattr(component, 'restart'):
            try:
                if asyncio.iscoroutinefunction(component.restart):
                    await component.restart()
                else:
                    component.restart()
                return True
            except Exception as e:
                logger.error(f"Default recovery failed: {e}")
                return False

        # 尝试stop + start
        if hasattr(component, 'stop') and hasattr(component, 'start'):
            try:
                if asyncio.iscoroutinefunction(component.stop):
                    await component.stop()
                else:
                    component.stop()

                if asyncio.iscoroutinefunction(component.start):
                    await component.start()
                else:
                    component.start()
                return True
            except Exception as e:
                logger.error(f"Default recovery (stop+start) failed: {e}")
                return False

        return False

    def _record_attempt(
        self,
        component: str,
        error: str,
        attempt_number: int,
        success: bool,
        backoff_delay: float,
    ) -> None:
        """记录恢复尝试

        Args:
            component: 组件名称
            error: 错误信息
            attempt_number: 尝试次数
            success: 是否成功
            backoff_delay: 退避延迟
        """
        attempt = RecoveryAttempt(
            component=component,
            error=error,
            attempt_number=attempt_number,
            timestamp=datetime.now(),
            success=success,
            backoff_delay=backoff_delay,
        )

        with self._lock:
            self._attempts.append(attempt)

            # 限制历史记录数量
            if len(self._attempts) > 1000:
                self._attempts = self._attempts[-500:]

    def reset_attempts(self, component_name: str) -> None:
        """重置组件的重试计数

        Args:
            component_name: 组件名称
        """
        with self._lock:
            if component_name in self._components:
                self._components[component_name].attempt_count = 0
                self._components[component_name].last_error = None
                logger.info(f"Reset attempts for {component_name}")

    def reset_all_attempts(self) -> None:
        """重置所有组件的重试计数"""
        with self._lock:
            for component_info in self._components.values():
                component_info.attempt_count = 0
                component_info.last_error = None
            logger.info("Reset all component attempts")

    def get_recovery_history(self) -> List[RecoveryAttempt]:
        """获取恢复历史

        Returns:
            恢复尝试列表
        """
        with self._lock:
            return self._attempts.copy()

    def get_component_status(self, component_name: str) -> Optional[Dict[str, Any]]:
        """获取组件状态

        Args:
            component_name: 组件名称

        Returns:
            组件状态字典
        """
        with self._lock:
            if component_name not in self._components:
                return None

            info = self._components[component_name]
            return {
                "name": info.name,
                "is_healthy": info.is_healthy,
                "attempt_count": info.attempt_count,
                "last_error": info.last_error,
                "last_recovery_at": info.last_recovery_at.isoformat() if info.last_recovery_at else None,
            }

    def get_all_component_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有组件状态

        Returns:
            组件状态字典
        """
        with self._lock:
            return {
                name: self.get_component_status(name)
                for name in self._components
            }

    def start_watchdog(self) -> None:
        """启动看门狗"""
        if self._is_watchdog_running:
            logger.warning("Watchdog is already running")
            return

        self._watchdog_stop_event.clear()
        self._is_watchdog_running = True

        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="RecoveryWatchdog"
        )
        self._watchdog_thread.start()

        logger.info("Recovery watchdog started")

    def stop_watchdog(self) -> None:
        """停止看门狗"""
        if not self._is_watchdog_running:
            return

        self._watchdog_stop_event.set()
        self._is_watchdog_running = False

        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5.0)
            self._watchdog_thread = None

        logger.info("Recovery watchdog stopped")

    def _watchdog_loop(self) -> None:
        """看门狗循环"""
        while not self._watchdog_stop_event.is_set():
            try:
                self._check_components()
            except Exception as e:
                logger.error(f"Watchdog error: {e}")

            self._watchdog_stop_event.wait(self.watchdog_interval)

    def _check_components(self) -> None:
        """检查所有组件健康状态"""
        with self._lock:
            components_to_check = list(self._components.values())

        for component_info in components_to_check:
            if component_info.health_check:
                try:
                    is_healthy = component_info.health_check()

                    with self._lock:
                        if component_info.name in self._components:
                            self._components[component_info.name].is_healthy = is_healthy

                    if not is_healthy:
                        logger.warning(f"Component {component_info.name} is unhealthy")

                except Exception as e:
                    logger.error(f"Health check failed for {component_info.name}: {e}")
                    with self._lock:
                        if component_info.name in self._components:
                            self._components[component_info.name].is_healthy = False

    def preserve_videos(self, videos: List[Any]) -> None:
        """保留视频列表

        Property 12: Video Preservation During Recovery
        恢复期间保留已检测的视频。

        Args:
            videos: 视频列表
        """
        with self._lock:
            self._preserved_videos = videos.copy()
            logger.info(f"Preserved {len(videos)} videos")

    def get_preserved_videos(self) -> List[Any]:
        """获取保留的视频列表

        Returns:
            视频列表
        """
        with self._lock:
            return self._preserved_videos.copy()

    def clear_preserved_videos(self) -> None:
        """清除保留的视频列表"""
        with self._lock:
            self._preserved_videos.clear()

    @property
    def is_watchdog_running(self) -> bool:
        """看门狗是否运行中"""
        return self._is_watchdog_running

    def get_errors_recovered_count(self) -> int:
        """获取成功恢复的错误数量

        Returns:
            成功恢复的数量
        """
        with self._lock:
            return sum(1 for a in self._attempts if a.success)
