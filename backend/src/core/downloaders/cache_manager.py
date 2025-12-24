"""
视频信息缓存管理器
减少重复的视频信息提取请求，提升性能
"""
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VideoInfoCache:
    """视频信息缓存管理器"""
    
    def __init__(self, cache_dir: str = "./cache/video_info", ttl_hours: int = 24, max_memory_items: int = 100):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            ttl_hours: 缓存有效期（小时）
            max_memory_items: 内存缓存最大条目数
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.max_memory_items = max_memory_items
        self._memory_cache = {}  # 内存缓存
    
    def _get_cache_key(self, url: str) -> str:
        """
        生成缓存键
        
        Args:
            url: 视频URL
            
        Returns:
            缓存键（URL的MD5哈希）
        """
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取视频信息
        
        Args:
            url: 视频URL
            
        Returns:
            缓存的视频信息，如果不存在或已过期则返回None
        """
        cache_key = self._get_cache_key(url)
        
        # 先检查内存缓存
        if cache_key in self._memory_cache:
            cache_data = self._memory_cache[cache_key]
            if self._is_valid(cache_data):
                logger.debug(f"Cache hit (memory): {url}")
                return cache_data['info']
            else:
                del self._memory_cache[cache_key]
        
        # 检查文件缓存
        cache_file = self._get_cache_file(cache_key)
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                if self._is_valid(cache_data):
                    logger.debug(f"Cache hit (file): {url}")
                    # 加载到内存缓存
                    self._memory_cache[cache_key] = cache_data
                    return cache_data['info']
                else:
                    # 过期，删除文件
                    cache_file.unlink()
                    logger.debug(f"Cache expired: {url}")
            except Exception as e:
                logger.error(f"Error reading cache: {e}")
        
        logger.debug(f"Cache miss: {url}")
        return None
    
    def set(self, url: str, info: Dict[str, Any]):
        """
        保存视频信息到缓存
        
        Args:
            url: 视频URL
            info: 视频信息
        """
        cache_key = self._get_cache_key(url)
        cache_data = {
            'url': url,
            'info': info,
            'timestamp': datetime.now().isoformat(),
        }
        
        # 保存到内存缓存（LRU策略）
        if len(self._memory_cache) >= self.max_memory_items:
            # 移除最旧的一个缓存项
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]
            logger.debug(f"Memory cache limit reached, removed oldest item")
        
        self._memory_cache[cache_key] = cache_data
        
        # 保存到文件缓存
        cache_file = self._get_cache_file(cache_key)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Cached video info: {url}")
        except Exception as e:
            logger.error(f"Error writing cache: {e}")
    
    def _is_valid(self, cache_data: Dict[str, Any]) -> bool:
        """
        检查缓存是否有效
        
        Args:
            cache_data: 缓存数据
            
        Returns:
            是否有效
        """
        try:
            timestamp = datetime.fromisoformat(cache_data['timestamp'])
            return datetime.now() - timestamp < self.ttl
        except Exception as e:
            logger.error(f"Error checking cache validity: {e}")
            return False
    
    def clear(self, url: Optional[str] = None):
        """
        清除缓存
        
        Args:
            url: 如果指定，只清除该URL的缓存；否则清除所有缓存
        """
        if url:
            # 清除特定URL的缓存
            cache_key = self._get_cache_key(url)
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
            
            cache_file = self._get_cache_file(cache_key)
            if cache_file.exists():
                cache_file.unlink()
            logger.info(f"Cleared cache for: {url}")
        else:
            # 清除所有缓存
            self._memory_cache.clear()
            for cache_file in self.cache_dir.glob('*.json'):
                cache_file.unlink()
            logger.info("Cleared all video info cache")
    
    def cleanup_expired(self):
        """清理过期的缓存文件"""
        count = 0
        for cache_file in self.cache_dir.glob('*.json'):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                if not self._is_valid(cache_data):
                    cache_file.unlink()
                    count += 1
            except Exception as e:
                logger.error(f"Error checking cache file {cache_file}: {e}")
        
        logger.info(f"Cleaned up {count} expired cache files")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        cache_files = list(self.cache_dir.glob('*.json'))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'cache_dir': str(self.cache_dir),
            'file_count': len(cache_files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'memory_cache_count': len(self._memory_cache),
            'ttl_hours': self.ttl.total_seconds() / 3600,
        }


# 全局缓存实例
_global_cache = None


def get_cache() -> VideoInfoCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = VideoInfoCache()
    return _global_cache
