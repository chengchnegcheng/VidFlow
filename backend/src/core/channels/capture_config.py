"""
捕获配置管理

管理透明捕获相关的配置，支持持久化和热更新。
"""

import json
import logging
from pathlib import Path
from typing import Optional, Callable, List
from threading import Lock

from .models import CaptureConfig, CaptureMode


logger = logging.getLogger(__name__)


# 默认配置文件路径
DEFAULT_CONFIG_PATH = "data/channels_capture_config.json"


class CaptureConfigManager:
    """捕获配置管理器
    
    负责配置的加载、保存和热更新通知。
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self._config_path = Path(config_path or DEFAULT_CONFIG_PATH)
        self._config: CaptureConfig = CaptureConfig()
        self._lock = Lock()
        self._on_config_changed: List[Callable[[CaptureConfig], None]] = []
        
        # 尝试加载现有配置
        self._load_config()
    
    @property
    def config(self) -> CaptureConfig:
        """获取当前配置"""
        with self._lock:
            return self._config
    
    def _load_config(self) -> None:
        """从文件加载配置"""
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._config = CaptureConfig.from_dict(data)
                    logger.info(f"Loaded capture config from {self._config_path}")
            else:
                logger.info("No existing capture config, using defaults")
        except Exception as e:
            logger.warning(f"Failed to load capture config: {e}, using defaults")
            self._config = CaptureConfig()
    
    def save_config(self) -> bool:
        """保存配置到文件
        
        Returns:
            保存成功返回 True
        """
        try:
            with self._lock:
                # 确保目录存在
                self._config_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(self._config_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)
                
                logger.info(f"Saved capture config to {self._config_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to save capture config: {e}")
            return False
    
    def update_config(self, **kwargs) -> CaptureConfig:
        """更新配置
        
        Args:
            **kwargs: 要更新的配置项
            
        Returns:
            更新后的配置
        """
        with self._lock:
            # 更新配置项
            if 'capture_mode' in kwargs:
                mode = kwargs['capture_mode']
                if isinstance(mode, str):
                    mode = CaptureMode(mode)
                self._config.capture_mode = mode
            
            if 'use_windivert' in kwargs:
                self._config.use_windivert = kwargs['use_windivert']
            
            if 'target_processes' in kwargs:
                self._config.target_processes = kwargs['target_processes']
            
            if 'no_detection_timeout' in kwargs:
                self._config.no_detection_timeout = kwargs['no_detection_timeout']
            
            if 'log_unrecognized_domains' in kwargs:
                self._config.log_unrecognized_domains = kwargs['log_unrecognized_domains']
            
            # 保存配置
            self.save_config()
            
            # 通知监听器
            config_copy = CaptureConfig.from_dict(self._config.to_dict())
        
        self._notify_config_changed(config_copy)
        return config_copy
    
    def set_config(self, config: CaptureConfig) -> None:
        """设置完整配置
        
        Args:
            config: 新配置
        """
        with self._lock:
            self._config = config
            self.save_config()
        
        self._notify_config_changed(config)
    
    def add_config_listener(self, callback: Callable[[CaptureConfig], None]) -> None:
        """添加配置变更监听器
        
        Args:
            callback: 配置变更时的回调函数
        """
        self._on_config_changed.append(callback)
    
    def remove_config_listener(self, callback: Callable[[CaptureConfig], None]) -> None:
        """移除配置变更监听器
        
        Args:
            callback: 要移除的回调函数
        """
        if callback in self._on_config_changed:
            self._on_config_changed.remove(callback)
    
    def _notify_config_changed(self, config: CaptureConfig) -> None:
        """通知配置变更
        
        Args:
            config: 新配置
        """
        for callback in self._on_config_changed:
            try:
                callback(config)
            except Exception as e:
                logger.error(f"Error in config change callback: {e}")
    
    def reset_to_defaults(self) -> CaptureConfig:
        """重置为默认配置
        
        Returns:
            默认配置
        """
        with self._lock:
            self._config = CaptureConfig()
            self.save_config()
        
        self._notify_config_changed(self._config)
        return self._config


# 全局配置管理器实例
_config_manager: Optional[CaptureConfigManager] = None


def get_config_manager() -> CaptureConfigManager:
    """获取全局配置管理器实例
    
    Returns:
        CaptureConfigManager 实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = CaptureConfigManager()
    return _config_manager
