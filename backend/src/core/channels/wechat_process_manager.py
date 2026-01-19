"""
微信进程管理器

管理微信进程识别和端口缓存。
支持进程监控、端口映射和进程重启检测。

Validates: Requirements 8.1, 8.2, 8.3, 8.6
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Set, Any
from dataclasses import dataclass, field

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from .models import WeChatProcess

logger = logging.getLogger(__name__)


class WeChatProcessManager:
    """微信进程管理器
    
    管理微信进程识别和端口缓存。
    
    Validates: Requirements 8.1, 8.2, 8.3, 8.6
    """
    
    # 微信相关进程名
    WECHAT_PROCESSES = [
        "WeChat.exe",
        "WeChatAppEx.exe",
        "WeChatApp.exe",
        "WeChatBrowser.exe",
        "WeChatPlayer.exe",
        "Weixin.exe",
        "WXWork.exe",
    ]
    
    def __init__(self, refresh_interval: float = 2.0):
        """初始化微信进程管理器
        
        Args:
            refresh_interval: 缓存刷新间隔（秒）
        """
        self._refresh_interval = refresh_interval
        
        # 进程缓存: pid -> WeChatProcess
        self._processes: Dict[int, WeChatProcess] = {}
        
        # 端口缓存: port -> pid
        self._port_cache: Dict[int, int] = {}
        
        # 监控线程
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_monitoring = False
        
        # 锁
        self._lock = threading.RLock()
        
        # 上次刷新时间
        self._last_refresh: Optional[datetime] = None
        
        # 进程重启检测
        self._known_pids: Set[int] = set()
        self._restart_callbacks: List[callable] = []
    
    def start_monitoring(self) -> None:
        """开始监控微信进程"""
        if self._is_monitoring:
            logger.warning("WeChat process monitoring is already running")
            return
        
        self._stop_event.clear()
        self._is_monitoring = True
        
        # 初始刷新
        self.refresh_cache()
        
        # 启动监控线程
        self._refresh_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="WeChatProcessMonitor"
        )
        self._refresh_thread.start()
        
        logger.info("WeChat process monitoring started")
    
    def stop_monitoring(self) -> None:
        """停止监控"""
        if not self._is_monitoring:
            return
        
        self._stop_event.set()
        self._is_monitoring = False
        
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5.0)
            self._refresh_thread = None
        
        logger.info("WeChat process monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                self.refresh_cache()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            # 等待下一次刷新
            self._stop_event.wait(self._refresh_interval)
    
    def refresh_cache(self) -> None:
        """刷新进程和端口缓存
        
        Property 10: WeChat Process Port Caching
        刷新后，is_wechat_port() 应该对所有当前微信进程使用的端口返回True。
        """
        if not HAS_PSUTIL:
            logger.warning("psutil not available, cannot refresh cache")
            return
        
        with self._lock:
            old_pids = set(self._processes.keys())
            new_processes: Dict[int, WeChatProcess] = {}
            new_port_cache: Dict[int, int] = {}
            
            try:
                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        proc_name = proc.info['name']
                        if not proc_name:
                            continue
                        
                        if not self._is_wechat_process(proc_name):
                            continue
                        
                        pid = proc.info['pid']
                        exe_path = proc.info.get('exe', '') or ''
                        
                        # 获取进程的网络连接
                        ports: Set[int] = set()
                        try:
                            connections = proc.net_connections(kind='inet')
                            for conn in connections:
                                if conn.laddr:
                                    ports.add(conn.laddr.port)
                                    new_port_cache[conn.laddr.port] = pid
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                        
                        # 创建或更新进程信息
                        if pid in self._processes:
                            # 更新现有进程
                            existing = self._processes[pid]
                            existing.ports = ports
                            existing.last_seen = datetime.now()
                            new_processes[pid] = existing
                        else:
                            # 新进程
                            new_processes[pid] = WeChatProcess(
                                pid=pid,
                                name=proc_name,
                                exe_path=exe_path,
                                ports=ports,
                                last_seen=datetime.now(),
                            )
                        
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # 更新缓存
                self._processes = new_processes
                self._port_cache = new_port_cache
                self._last_refresh = datetime.now()
                
                # 检测进程重启
                new_pids = set(new_processes.keys())
                self._detect_restart(old_pids, new_pids)
                
                logger.debug(f"Refreshed cache: {len(new_processes)} processes, "
                           f"{len(new_port_cache)} ports")
                
            except Exception as e:
                logger.error(f"Failed to refresh cache: {e}")
    
    def _detect_restart(self, old_pids: Set[int], new_pids: Set[int]) -> None:
        """检测进程重启
        
        Args:
            old_pids: 旧的PID集合
            new_pids: 新的PID集合
        """
        # 检测新启动的进程
        started_pids = new_pids - old_pids
        # 检测已退出的进程
        stopped_pids = old_pids - new_pids
        
        if started_pids or stopped_pids:
            # 如果有进程变化，可能是重启
            if self._known_pids and started_pids and stopped_pids:
                logger.info(f"WeChat process restart detected: "
                          f"stopped={stopped_pids}, started={started_pids}")
                
                # 调用重启回调
                for callback in self._restart_callbacks:
                    try:
                        callback(stopped_pids, started_pids)
                    except Exception as e:
                        logger.error(f"Error in restart callback: {e}")
        
        self._known_pids = new_pids
    
    def _is_wechat_process(self, process_name: str) -> bool:
        """检查是否是微信进程
        
        Args:
            process_name: 进程名
            
        Returns:
            是否是微信进程
        """
        if not process_name:
            return False
        
        process_name_lower = process_name.lower()
        for wechat_proc in self.WECHAT_PROCESSES:
            if wechat_proc.lower() == process_name_lower:
                return True
        
        return False
    
    def get_processes(self) -> List[WeChatProcess]:
        """获取所有微信进程
        
        Returns:
            微信进程列表
        """
        with self._lock:
            return list(self._processes.values())
    
    def is_wechat_port(self, port: int) -> bool:
        """检查端口是否属于微信进程
        
        Property 10: WeChat Process Port Caching
        在缓存刷新后，此方法应该对所有当前微信进程使用的端口返回True。
        
        Args:
            port: 端口号
            
        Returns:
            是否属于微信进程
        """
        with self._lock:
            return port in self._port_cache
    
    def is_wechat_running(self) -> bool:
        """检查微信是否在运行
        
        Returns:
            微信是否在运行
        """
        with self._lock:
            return len(self._processes) > 0
    
    def get_process_by_port(self, port: int) -> Optional[WeChatProcess]:
        """根据端口获取进程
        
        Args:
            port: 端口号
            
        Returns:
            微信进程，如果不存在则返回None
        """
        with self._lock:
            pid = self._port_cache.get(port)
            if pid:
                return self._processes.get(pid)
            return None
    
    def get_process_by_pid(self, pid: int) -> Optional[WeChatProcess]:
        """根据PID获取进程
        
        Args:
            pid: 进程ID
            
        Returns:
            微信进程，如果不存在则返回None
        """
        with self._lock:
            return self._processes.get(pid)
    
    def get_all_ports(self) -> Set[int]:
        """获取所有微信进程使用的端口
        
        Returns:
            端口集合
        """
        with self._lock:
            return set(self._port_cache.keys())
    
    def get_port_count(self) -> int:
        """获取端口数量
        
        Returns:
            端口数量
        """
        with self._lock:
            return len(self._port_cache)
    
    def get_process_count(self) -> int:
        """获取进程数量
        
        Returns:
            进程数量
        """
        with self._lock:
            return len(self._processes)
    
    def add_restart_callback(self, callback: callable) -> None:
        """添加进程重启回调
        
        Args:
            callback: 回调函数，接收 (stopped_pids, started_pids) 参数
        """
        self._restart_callbacks.append(callback)
    
    def remove_restart_callback(self, callback: callable) -> None:
        """移除进程重启回调
        
        Args:
            callback: 回调函数
        """
        if callback in self._restart_callbacks:
            self._restart_callbacks.remove(callback)
    
    def clear_cache(self) -> None:
        """清除缓存"""
        with self._lock:
            self._processes.clear()
            self._port_cache.clear()
            self._known_pids.clear()
            self._last_refresh = None
    
    def get_last_refresh_time(self) -> Optional[datetime]:
        """获取上次刷新时间
        
        Returns:
            上次刷新时间
        """
        return self._last_refresh
    
    @property
    def is_monitoring(self) -> bool:
        """是否正在监控"""
        return self._is_monitoring
    
    @property
    def refresh_interval(self) -> float:
        """刷新间隔"""
        return self._refresh_interval
    
    @refresh_interval.setter
    def refresh_interval(self, value: float) -> None:
        """设置刷新间隔"""
        if value > 0:
            self._refresh_interval = value
