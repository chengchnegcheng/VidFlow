"""
QUIC协议管理器

管理QUIC协议阻止，强制回退到TCP。
仅针对微信进程的QUIC流量进行选择性阻止。

Validates: Requirements 4.1, 4.3, 4.4
"""

import asyncio
import logging
from typing import Optional, List, Set, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from threading import Event, Thread

from .process_targets import QUIC_BLOCK_TARGET_PROCESSES, dedupe_process_names

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger(__name__)


@dataclass
class QUICBlockStats:
    """QUIC阻止统计"""
    packets_blocked: int = 0
    packets_allowed: int = 0
    last_blocked_at: Optional[datetime] = None
    blocked_ports: Set[int] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "packets_blocked": self.packets_blocked,
            "packets_allowed": self.packets_allowed,
            "last_blocked_at": self.last_blocked_at.isoformat() if self.last_blocked_at else None,
            "blocked_ports": list(self.blocked_ports),
        }


class QUICManager:
    """QUIC协议管理器
    
    通过WinDivert阻止微信进程的QUIC流量，强制其回退到TCP。
    仅阻止目标进程的UDP 443端口流量。
    
    Validates: Requirements 4.1, 4.3, 4.4
    """
    
    # QUIC使用的端口
    QUIC_PORT = 443
    
    # 默认目标进程
    DEFAULT_TARGET_PROCESSES = list(QUIC_BLOCK_TARGET_PROCESSES)
    
    def __init__(
        self,
        target_processes: Optional[List[str]] = None,
        on_packet_blocked: Optional[Callable[[int, str, int], None]] = None,
    ):
        """初始化QUIC管理器
        
        Args:
            target_processes: 目标进程列表，默认为微信相关进程
            on_packet_blocked: 包被阻止时的回调函数(src_port, dst_ip, dst_port)
        """
        self.target_processes = dedupe_process_names(
            target_processes or self.DEFAULT_TARGET_PROCESSES
        )
        self._on_packet_blocked = on_packet_blocked
        
        self._is_blocking = False
        self._block_handle = None
        self._block_thread: Optional[Thread] = None
        self._stop_event = Event()
        
        # 统计信息
        self._stats = QUICBlockStats()
        
        # 端口到进程的缓存
        self._port_to_pid: Dict[int, int] = {}
        self._wechat_pids: Set[int] = set()
        self._cache_refresh_interval = 2.0  # 秒
        self._last_cache_refresh: Optional[datetime] = None
    
    @property
    def is_blocking(self) -> bool:
        """是否正在阻止QUIC流量"""
        return self._is_blocking
    
    def get_stats(self) -> QUICBlockStats:
        """获取阻止统计"""
        return self._stats
    
    def get_blocked_count(self) -> int:
        """获取已阻止的包数量"""
        return self._stats.packets_blocked
    
    async def start_blocking(self) -> bool:
        """开始阻止QUIC流量
        
        Returns:
            是否成功启动阻止
        """
        if self._is_blocking:
            logger.warning("QUIC blocking is already running")
            return True
        
        try:
            # 刷新进程缓存（同步 psutil 操作，卸载到线程池）
            await asyncio.to_thread(self._refresh_process_cache)

            # 尝试加载WinDivert（可能涉及 DLL 加载，卸载到线程池）
            if not await asyncio.to_thread(self._init_windivert):
                logger.error("Failed to initialize WinDivert for QUIC blocking")
                return False
            
            self._is_blocking = True
            self._stop_event.clear()
            
            # 启动阻止任务
            self._block_thread = Thread(target=self._blocking_loop, daemon=True)
            self._block_thread.start()
            
            logger.info(f"QUIC blocking started for processes: {self.target_processes}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start QUIC blocking: {e}")
            self._is_blocking = False
            return False
    
    async def stop_blocking(self) -> bool:
        """停止阻止QUIC流量
        
        Returns:
            是否成功停止阻止
        """
        if not self._is_blocking:
            return True
        
        try:
            self._stop_event.set()
            self._is_blocking = False

            self._cleanup_windivert()

            # 等待阻止线程退出（在线程池中 join，避免阻塞事件循环）
            block_thread = self._block_thread
            if block_thread and block_thread.is_alive():
                await asyncio.to_thread(block_thread.join, 2.0)
            self._block_thread = None
            
            logger.info("QUIC blocking stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop QUIC blocking: {e}")
            self._is_blocking = False
            return False
    
    def should_block_packet(
        self,
        src_port: int,
        dst_ip: str,
        dst_port: int,
        protocol: str = "udp",
    ) -> bool:
        """判断是否应该阻止此UDP包
        
        Property 6: QUIC Selective Blocking
        对于任何UDP 443端口的包，仅当以下条件都满足时才阻止：
        1. QUIC阻止已启用
        2. 源端口属于微信进程
        
        Args:
            src_port: 源端口
            dst_ip: 目标IP
            dst_port: 目标端口
            protocol: 协议类型
            
        Returns:
            是否应该阻止
        """
        # 条件1: QUIC阻止必须启用
        if not self._is_blocking:
            return False
        
        # 条件2: 必须是UDP协议
        if protocol.lower() != "udp":
            return False
        
        # 条件3: 必须是QUIC端口(443)
        if dst_port != self.QUIC_PORT:
            return False
        
        # 条件4: 源端口必须属于微信进程
        if not self._is_wechat_port(src_port):
            self._stats.packets_allowed += 1
            return False
        
        # 满足所有条件，应该阻止
        self._stats.packets_blocked += 1
        self._stats.last_blocked_at = datetime.now()
        self._stats.blocked_ports.add(src_port)
        
        if self._on_packet_blocked:
            try:
                self._on_packet_blocked(src_port, dst_ip, dst_port)
            except Exception as e:
                logger.error(f"Error in packet blocked callback: {e}")
        
        return True
    
    def _is_wechat_port(self, port: int) -> bool:
        """检查端口是否属于微信进程
        
        Args:
            port: 端口号
            
        Returns:
            是否属于微信进程
        """
        # 首先检查端口是否在缓存中（不刷新缓存）
        if port in self._port_to_pid:
            pid = self._port_to_pid[port]
            return pid in self._wechat_pids
        
        # 端口不在缓存中，尝试实时查找
        return self._lookup_port_process(port)
    
    def _maybe_refresh_cache(self) -> None:
        """如果需要则刷新缓存"""
        now = datetime.now()
        if (self._last_cache_refresh is None or 
            (now - self._last_cache_refresh).total_seconds() > self._cache_refresh_interval):
            self._refresh_process_cache()
    
    def _refresh_process_cache(self) -> None:
        """刷新进程和端口缓存"""
        if not HAS_PSUTIL:
            return
        
        try:
            self._wechat_pids.clear()
            self._port_to_pid.clear()
            
            # 查找微信进程
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and self._is_target_process(proc_name):
                        pid = proc.info['pid']
                        self._wechat_pids.add(pid)
                        
                        # 获取进程的网络连接
                        try:
                            connections = proc.net_connections(kind='udp')
                            for conn in connections:
                                if conn.laddr:
                                    self._port_to_pid[conn.laddr.port] = pid
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self._last_cache_refresh = datetime.now()
            logger.debug(f"Refreshed cache: {len(self._wechat_pids)} WeChat processes, "
                        f"{len(self._port_to_pid)} ports")
            
        except Exception as e:
            logger.error(f"Failed to refresh process cache: {e}")
    
    def _lookup_port_process(self, port: int) -> bool:
        """实时查找端口所属进程
        
        Args:
            port: 端口号
            
        Returns:
            是否属于微信进程
        """
        if not HAS_PSUTIL:
            return False
        
        try:
            for conn in psutil.net_connections(kind='udp'):
                if conn.laddr and conn.laddr.port == port and conn.pid:
                    # 缓存结果
                    self._port_to_pid[port] = conn.pid
                    
                    # 检查是否是微信进程
                    if conn.pid in self._wechat_pids:
                        return True
                    
                    # 检查进程名
                    try:
                        proc = psutil.Process(conn.pid)
                        if self._is_target_process(proc.name()):
                            self._wechat_pids.add(conn.pid)
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to lookup port process: {e}")
            return False
    
    def _is_target_process(self, process_name: str) -> bool:
        """检查是否是目标进程
        
        Args:
            process_name: 进程名
            
        Returns:
            是否是目标进程
        """
        if not process_name:
            return False
        
        process_name_lower = process_name.lower()
        for target in self.target_processes:
            if target.lower() == process_name_lower:
                return True
        
        return False
    
    def _init_windivert(self) -> bool:
        """初始化WinDivert
        
        Returns:
            是否成功初始化
        """
        try:
            import pydivert
            
            # 创建WinDivert过滤器：捕获所有UDP 443流量
            filter_str = f"udp.DstPort == {self.QUIC_PORT} and outbound"
            
            self._block_handle = pydivert.WinDivert(filter_str)
            self._block_handle.open()
            
            logger.info(f"WinDivert initialized with filter: {filter_str}")
            return True
            
        except ImportError:
            logger.warning("pydivert not available, QUIC blocking will be simulated")
            return True  # 允许模拟模式
        except Exception as e:
            logger.error(f"Failed to initialize WinDivert: {e}")
            return False
    
    def _cleanup_windivert(self) -> None:
        """清理WinDivert资源"""
        if self._block_handle:
            try:
                self._block_handle.close()
            except Exception as e:
                logger.error(f"Error closing WinDivert handle: {e}")
            finally:
                self._block_handle = None
    
    def _blocking_loop(self) -> None:
        """阻止循环"""
        try:
            if self._block_handle is None:
                # 模拟模式：只定期刷新缓存
                while not self._stop_event.is_set():
                    self._refresh_process_cache()
                    if self._stop_event.wait(timeout=self._cache_refresh_interval):
                        break
                return
            
            # 实际WinDivert模式
            while not self._stop_event.is_set():
                try:
                    # 非阻塞接收
                    packet = self._block_handle.recv()
                    
                    if packet:
                        src_port = packet.src_port
                        dst_ip = packet.dst_addr
                        dst_port = packet.dst_port
                        
                        if self.should_block_packet(src_port, dst_ip, dst_port, "udp"):
                            # 丢弃包（不重新注入）
                            logger.debug(f"Blocked QUIC packet: {src_port} -> {dst_ip}:{dst_port}")
                        else:
                            # 重新注入包
                            self._block_handle.send(packet)
                    
                except Exception as e:
                    if not self._stop_event.is_set():
                        logger.error(f"Error in blocking loop: {e}")
                    if self._stop_event.wait(timeout=0.1):
                        break
                    
        except Exception as e:
            logger.error(f"Blocking loop error: {e}")
    
    def add_target_process(self, process_name: str) -> None:
        """添加目标进程
        
        Args:
            process_name: 进程名
        """
        if process_name and process_name not in self.target_processes:
            self.target_processes.append(process_name)
            logger.info(f"Added target process: {process_name}")
    
    def remove_target_process(self, process_name: str) -> None:
        """移除目标进程
        
        Args:
            process_name: 进程名
        """
        if process_name in self.target_processes:
            self.target_processes.remove(process_name)
            logger.info(f"Removed target process: {process_name}")
    
    def get_target_processes(self) -> List[str]:
        """获取目标进程列表"""
        return self.target_processes.copy()
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self._stats = QUICBlockStats()
        logger.info("QUIC blocking stats reset")
