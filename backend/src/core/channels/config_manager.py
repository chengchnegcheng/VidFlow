"""
配置管理器

管理捕获配置的加载、保存、验证和导入导出。
支持配置持久化和默认值回退。

Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .models import MultiModeCaptureConfig, CaptureMode

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器
    
    管理捕获配置的加载、保存、验证和导入导出。
    
    Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
    """
    
    DEFAULT_CONFIG_FILENAME = "capture_config.json"
    BACKUP_SUFFIX = ".backup"
    
    def __init__(self, config_path: Optional[Path] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_path is None:
            # 默认配置路径
            config_path = Path.home() / ".vidflow" / self.DEFAULT_CONFIG_FILENAME
        
        self.config_path = Path(config_path)
        self._config: MultiModeCaptureConfig = MultiModeCaptureConfig.get_defaults()
        self._last_load_time: Optional[datetime] = None
        self._last_save_time: Optional[datetime] = None
    
    def load(self) -> MultiModeCaptureConfig:
        """加载配置
        
        Property 13: Configuration Persistence Round-Trip
        加载保存的配置应该产生等效的配置对象。
        
        Returns:
            加载的配置，如果加载失败则返回默认配置
        """
        if not self.config_path.exists():
            logger.info(f"Config file not found: {self.config_path}, using defaults")
            self._config = MultiModeCaptureConfig.get_defaults()
            return self._config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._config = MultiModeCaptureConfig.from_dict(data)
            self._last_load_time = datetime.now()
            
            # 验证加载的配置
            errors = self._config.validate()
            if errors:
                logger.warning(f"Loaded config has validation errors: {errors}")
            
            logger.info(f"Config loaded from {self.config_path}")
            return self._config
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config file: {e}")
            self._config = MultiModeCaptureConfig.get_defaults()
            return self._config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config = MultiModeCaptureConfig.get_defaults()
            return self._config
    
    def save(self, config: Optional[MultiModeCaptureConfig] = None) -> bool:
        """保存配置
        
        Property 13: Configuration Persistence Round-Trip
        保存配置后重新加载应该产生等效的配置对象。
        
        Args:
            config: 要保存的配置，如果为None则保存当前配置
            
        Returns:
            是否保存成功
        """
        if config is not None:
            self._config = config
        
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建备份
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix(
                    self.config_path.suffix + self.BACKUP_SUFFIX
                )
                shutil.copy2(self.config_path, backup_path)
            
            # 保存配置
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)
            
            self._last_save_time = datetime.now()
            logger.info(f"Config saved to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def export_config(self, export_path: Path) -> bool:
        """导出配置
        
        Args:
            export_path: 导出路径
            
        Returns:
            是否导出成功
        """
        try:
            export_path = Path(export_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"Config exported to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            return False
    
    def import_config(self, import_path: Path) -> Optional[MultiModeCaptureConfig]:
        """导入配置
        
        Args:
            import_path: 导入路径
            
        Returns:
            导入的配置，如果导入失败则返回None
        """
        try:
            import_path = Path(import_path)
            
            if not import_path.exists():
                logger.error(f"Import file not found: {import_path}")
                return None
            
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            config = MultiModeCaptureConfig.from_dict(data)
            
            # 验证导入的配置
            errors = config.validate()
            if errors:
                logger.warning(f"Imported config has validation errors: {errors}")
            
            self._config = config
            logger.info(f"Config imported from {import_path}")
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse import file: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            return None
    
    def reset_to_defaults(self) -> MultiModeCaptureConfig:
        """重置为默认值
        
        Returns:
            默认配置
        """
        self._config = MultiModeCaptureConfig.get_defaults()
        logger.info("Config reset to defaults")
        return self._config
    
    def get_config(self) -> MultiModeCaptureConfig:
        """获取当前配置
        
        Returns:
            当前配置
        """
        return self._config
    
    def set_config(self, config: MultiModeCaptureConfig) -> None:
        """设置当前配置
        
        Args:
            config: 新配置
        """
        self._config = config
    
    def update_config(self, **kwargs) -> MultiModeCaptureConfig:
        """更新配置的部分字段
        
        Args:
            **kwargs: 要更新的字段
            
        Returns:
            更新后的配置
        """
        config_dict = self._config.to_dict()
        config_dict.update(kwargs)
        self._config = MultiModeCaptureConfig.from_dict(config_dict)
        return self._config
    
    def validate_config(self, config: Optional[MultiModeCaptureConfig] = None) -> List[str]:
        """验证配置
        
        Property 14: Configuration Validation
        对于任何配置字典，validate()函数应该对有效配置返回空列表，
        对无效配置返回非空错误消息列表。
        
        Args:
            config: 要验证的配置，如果为None则验证当前配置
            
        Returns:
            错误消息列表，空列表表示配置有效
        """
        if config is None:
            config = self._config
        
        return config.validate()
    
    def is_valid(self, config: Optional[MultiModeCaptureConfig] = None) -> bool:
        """检查配置是否有效
        
        Args:
            config: 要检查的配置，如果为None则检查当前配置
            
        Returns:
            配置是否有效
        """
        errors = self.validate_config(config)
        return len(errors) == 0
    
    @property
    def last_load_time(self) -> Optional[datetime]:
        """上次加载时间"""
        return self._last_load_time
    
    @property
    def last_save_time(self) -> Optional[datetime]:
        """上次保存时间"""
        return self._last_save_time
    
    def config_exists(self) -> bool:
        """检查配置文件是否存在
        
        Returns:
            配置文件是否存在
        """
        return self.config_path.exists()
    
    def delete_config(self) -> bool:
        """删除配置文件
        
        Returns:
            是否删除成功
        """
        try:
            if self.config_path.exists():
                self.config_path.unlink()
                logger.info(f"Config file deleted: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete config: {e}")
            return False
    
    def get_backup_path(self) -> Path:
        """获取备份文件路径
        
        Returns:
            备份文件路径
        """
        return self.config_path.with_suffix(
            self.config_path.suffix + self.BACKUP_SUFFIX
        )
    
    def restore_from_backup(self) -> bool:
        """从备份恢复配置
        
        Returns:
            是否恢复成功
        """
        backup_path = self.get_backup_path()
        
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        try:
            shutil.copy2(backup_path, self.config_path)
            self.load()
            logger.info(f"Config restored from backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False
