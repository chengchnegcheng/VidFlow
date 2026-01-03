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
        self.paused_tasks: Set[str] = set()  # 暂停的任务
        self.paused_task_info: Dict[str, dict] = {}  # 暂停任务的信息（用于恢复）
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
            
            # 从暂停列表中移除（如果存在）
            self.paused_tasks.discard(task_id)
            self.paused_task_info.pop(task_id, None)
            
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
    
    async def pause_task(self, task_id: str, task_info: dict = None) -> bool:
        """
        暂停任务
        
        Args:
            task_id: 任务ID
            task_info: 任务信息（用于恢复时重新下载）
            
        Returns:
            是否成功暂停
        """
        async with self._lock:
            # 检查任务是否已取消
            if task_id in self.cancelled_tasks:
                logger.warning(f"Task {task_id} is cancelled, cannot pause")
                return False
            
            # 标记为暂停
            self.paused_tasks.add(task_id)
            
            # 保存任务信息用于恢复
            if task_info:
                self.paused_task_info[task_id] = task_info
            
            # 如果任务正在运行，取消它
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                if not task.done():
                    task.cancel()
                    logger.info(f"Sent pause signal to running task {task_id}")
            
            # 从活跃任务中移除
            if task_id in self.active_tasks:
                self.active_tasks.remove(task_id)
                logger.info(f"Task {task_id} paused and removed from active tasks")
            
            return True
    
    async def resume_task(self, task_id: str) -> dict | None:
        """
        恢复暂停的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息（用于重新开始下载），如果任务不在暂停列表则返回 None
        """
        async with self._lock:
            if task_id not in self.paused_tasks:
                logger.warning(f"Task {task_id} is not paused")
                return None
            
            # 从暂停列表移除
            self.paused_tasks.discard(task_id)
            
            # 获取保存的任务信息
            task_info = self.paused_task_info.pop(task_id, None)
            
            logger.info(f"Task {task_id} resumed")
            return task_info
    
    async def is_task_paused(self, task_id: str) -> bool:
        """
        检查任务是否已暂停
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否已暂停
        """
        async with self._lock:
            return task_id in self.paused_tasks
    
    def is_task_paused_sync(self, task_id: str) -> bool:
        """
        同步检查任务是否已暂停（用于 progress_hook）
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否已暂停
        """
        return task_id in self.paused_tasks
    
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

    async def add_task(self, task_id: str, priority: int = 0) -> bool:
        """
        添加任务到队列
        
        Args:
            task_id: 任务ID
            priority: 优先级（数字越大优先级越高）
            
        Returns:
            是否成功添加
        """
        async with self._lock:
            # 检查任务是否已存在
            if task_id in self.task_info:
                logger.warning(f"Task {task_id} already in queue")
                return False
            
            # 检查是否已取消
            if task_id in self.cancelled_tasks:
                logger.warning(f"Task {task_id} was cancelled, not adding to queue")
                return False
            
            # 创建任务信息
            queue_task = QueueTask(task_id=task_id, priority=priority)
            self.task_info[task_id] = queue_task
            
            # 添加到等待队列
            await self.pending_queue.put(task_id)
            
            logger.info(f"Task {task_id} added to queue. Pending: {self.pending_queue.qsize()}")
            return True

    async def start_next_task(self) -> str | None:
        """
        启动下一个等待中的任务
        
        Returns:
            启动的任务ID，如果没有可启动的任务则返回 None
        """
        async with self._lock:
            # 检查是否有空闲槽位
            if len(self.active_tasks) >= self.max_concurrent:
                logger.debug(f"No available slots. Active: {len(self.active_tasks)}/{self.max_concurrent}")
                return None
            
            # 检查是否有等待中的任务
            if self.pending_queue.empty():
                logger.debug("No pending tasks in queue")
                return None
            
            # 获取下一个任务
            try:
                task_id = self.pending_queue.get_nowait()
            except asyncio.QueueEmpty:
                return None
            
            # 检查任务是否已取消
            if task_id in self.cancelled_tasks:
                logger.info(f"Task {task_id} was cancelled, skipping")
                if task_id in self.task_info:
                    del self.task_info[task_id]
                # 递归获取下一个任务
                return await self._start_next_task_unlocked()
            
            # 将任务标记为活跃
            self.active_tasks.add(task_id)
            
            logger.info(f"Task {task_id} started. Active: {len(self.active_tasks)}/{self.max_concurrent}")
            return task_id

    async def _start_next_task_unlocked(self) -> str | None:
        """内部方法：在已持有锁的情况下启动下一个任务"""
        # 检查是否有空闲槽位
        if len(self.active_tasks) >= self.max_concurrent:
            return None
        
        # 检查是否有等待中的任务
        if self.pending_queue.empty():
            return None
        
        # 获取下一个任务
        try:
            task_id = self.pending_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
        
        # 检查任务是否已取消
        if task_id in self.cancelled_tasks:
            if task_id in self.task_info:
                del self.task_info[task_id]
            # 递归获取下一个任务
            return await self._start_next_task_unlocked()
        
        # 将任务标记为活跃
        self.active_tasks.add(task_id)
        
        logger.info(f"Task {task_id} started. Active: {len(self.active_tasks)}/{self.max_concurrent}")
        return task_id

    async def complete_task(self, task_id: str):
        """
        标记任务完成并从队列中移除
        
        Args:
            task_id: 任务ID
        """
        async with self._lock:
            # 从活跃任务中移除
            if task_id in self.active_tasks:
                self.active_tasks.remove(task_id)
                logger.info(f"Task {task_id} completed. Active: {len(self.active_tasks)}/{self.max_concurrent}")
            
            # 从任务信息中移除
            if task_id in self.task_info:
                del self.task_info[task_id]
            
            # 从运行中任务中移除
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            # 从取消列表中移除（如果存在）
            self.cancelled_tasks.discard(task_id)
            
            # 从暂停列表中移除（如果存在）
            self.paused_tasks.discard(task_id)
            self.paused_task_info.pop(task_id, None)

    async def is_task_cancelled(self, task_id: str) -> bool:
        """
        检查任务是否已被取消
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否已取消
        """
        async with self._lock:
            return task_id in self.cancelled_tasks
    
    def is_task_cancelled_sync(self, task_id: str) -> bool:
        """
        同步检查任务是否已被取消（用于 yt-dlp 的 progress_hook）
        
        注意：这个方法不使用锁，可能有轻微的竞态条件，
        但对于取消检查来说是可以接受的。
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否已取消
        """
        return task_id in self.cancelled_tasks


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
