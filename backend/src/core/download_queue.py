"""
下载队列管理器 - 控制并发下载数量
"""
import asyncio
import logging
from typing import Dict, Set
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class QueueTask:
    """队列任务"""
    task_id: str
    priority: int = 0
    added_at: datetime = None
    
    def __post_init__(self):
        if self.added_at is None:
            self.added_at = datetime.now()


class DownloadQueue:
    """下载队列管理器"""
    
    def __init__(self, max_concurrent: int = 3):
        """
        初始化队列管理器
        
        Args:
            max_concurrent: 最大并发下载数
        """
        self.max_concurrent = max_concurrent
        self.active_tasks: Set[str] = set()  # 正在下载的任务
        self.pending_queue: asyncio.Queue = asyncio.Queue()  # 等待队列
        self.task_info: Dict[str, QueueTask] = {}  # 任务信息
        self.cancelled_tasks: Set[str] = set()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        logger.info(f"Download queue initialized with max_concurrent={max_concurrent}")

    async def register_running_task(self, task_id: str, task: asyncio.Task):
        async with self._lock:
            self.running_tasks[task_id] = task
            
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
        """
        async with self._lock:
            # 标记为取消
            self.cancelled_tasks.add(task_id)
            
            # 1. 如果任务正在运行，强制取消 asyncio.Task
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                if not task.done():
                    task.cancel()  # 发送取消信号
                    logger.info(f"Sent cancel signal to running task {task_id}")
                # 从运行列表中移除（实际移除会在 task done callback 中处理，这里先移除以防止重复取消）
                # self.running_tasks.pop(task_id, None) 
                
            # 2. 如果任务在活跃列表中，移除
            if task_id in self.active_tasks:
                self.active_tasks.remove(task_id)
                logger.info(f"Task {task_id} removed from active tasks")
            
            # 3. 如果任务在队列信息中，移除
            if task_id in self.task_info:
                del self.task_info[task_id]
                logger.info(f"Task {task_id} removed from queue info")

            return True
    
    async def get_status(self) -> dict:
        """
        获取队列状态
        
        Returns:
            队列状态信息
        """
        async with self._lock:
            return {
                'max_concurrent': self.max_concurrent,
                'active_count': len(self.active_tasks),
                'pending_count': self.pending_queue.qsize(),
                'active_tasks': list(self.active_tasks),
                'available_slots': max(0, self.max_concurrent - len(self.active_tasks))
            }
    
    async def update_max_concurrent(self, max_concurrent: int):
        """
        更新最大并发数
        
        Args:
            max_concurrent: 新的最大并发数
        """
        async with self._lock:
            old_value = self.max_concurrent
            self.max_concurrent = max(1, max_concurrent)
            logger.info(f"Max concurrent updated: {old_value} -> {self.max_concurrent}")


# 全局队列实例
_download_queue: DownloadQueue | None = None


def get_download_queue(max_concurrent: int = 3) -> DownloadQueue:
    """
    获取全局下载队列实例
    
    Args:
        max_concurrent: 最大并发数（仅在首次创建时使用）
        
    Returns:
        下载队列实例
    """
    global _download_queue
    if _download_queue is None:
        _download_queue = DownloadQueue(max_concurrent=max_concurrent)
    return _download_queue
