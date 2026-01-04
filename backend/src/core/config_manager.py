"""
配置管理器 - 持久化用户配置
"""
import os
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

CONFIG_VERSION = "1.0.0"

# 配置文件路径（支持打包后的环境）
if getattr(sys, 'frozen', False):
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        BASE_DIR = Path(appdata) / 'VidFlow'
    elif sys.platform == 'darwin':
        BASE_DIR = Path.home() / 'Library' / 'Application Support' / 'VidFlow'
    else:
        BASE_DIR = Path.home() / '.local' / 'share' / 'VidFlow'
    BASE_DIR.mkdir(parents=True, exist_ok=True)
else:
    BASE_DIR = Path(__file__).parent.parent.parent

DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"

# 获取系统默认下载文件夹
def get_default_download_path() -> str:
    """获取系统默认下载文件夹路径，使用 VidFlow 子目录"""
    try:
        # Windows: C:\Users\{username}\Downloads\VidFlow
        # macOS/Linux: ~/Downloads/VidFlow
        home = Path.home()
        downloads = home / "Downloads"
        
        # 如果 Downloads 文件夹存在，使用它下面的 VidFlow 子目录
        if downloads.exists():
            vidflow_dir = downloads / "VidFlow"
            vidflow_dir.mkdir(parents=True, exist_ok=True)
            return str(vidflow_dir)
        
        # 否则使用当前工作目录的 downloads 文件夹
        fallback = BASE_DIR / "data" / "downloads"
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)
    except Exception as e:
        logger.error(f"Failed to get default download path: {e}")
        # 最后的后备方案
        fallback = BASE_DIR / "data" / "downloads"
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)

# 默认配置
def get_default_config() -> Dict[str, Any]:
    """获取默认配置，包含动态生成的默认下载路径"""
    return {
        "_config_version": CONFIG_VERSION,
        "app": {
            "version": "3.1.0",
            "first_run": True,
            "language": "zh-CN",
            "theme": "light",
        },
        "download": {
            "default_path": get_default_download_path(),  # 使用系统默认下载文件夹
            "default_quality": "1080p",
            "default_format": "mp4",
            "max_concurrent": 3,
            "auto_subtitle": False,
            "auto_translate": False,
        },
        "subtitle": {
            "default_model": "base",
            "default_source_lang": "auto",
            "default_target_langs": ["zh"],
            "max_concurrent": 1,
        },
        "advanced": {
            "proxy": {
                "enabled": False,
                "type": "http",
                "host": "",
                "port": 0,
                "username": "",
                "password": ""
            },
            "notifications": True,
            "auto_update": True,
            "save_history": True,
            "log_level": "INFO",
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    }


def migrate_config(old_config: Dict[str, Any], old_version: str) -> Dict[str, Any]:
    migrated = dict(old_config) if isinstance(old_config, dict) else {}

    try:
        download_cfg = migrated.get("download")
        if isinstance(download_cfg, dict):
            current_path = download_cfg.get("default_path")
            if current_path is None or (isinstance(current_path, str) and not current_path.strip()):
                download_cfg["default_path"] = get_default_download_path()
    except Exception as e:
        logger.warning(f"Failed to migrate config from version {old_version}: {e}")

    return migrated


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，默认使用 CONFIG_FILE
        """
        self.config_file = config_file or CONFIG_FILE
        self.config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    config_version = "0.0.0"
                    if isinstance(loaded_config, dict):
                        config_version = str(loaded_config.get('_config_version', '0.0.0'))
                    else:
                        loaded_config = {}

                    if config_version != CONFIG_VERSION:
                        loaded_config = migrate_config(loaded_config, config_version)
                        if isinstance(loaded_config, dict):
                            loaded_config['_config_version'] = CONFIG_VERSION

                    # 合并默认配置和用户配置（用户配置优先）
                    self.config = self._merge_config(get_default_config(), loaded_config)
                    logger.info(f"Configuration loaded from {self.config_file}")

                    if config_version != CONFIG_VERSION:
                        self.save_config()
            else:
                # 首次运行，创建默认配置
                self.config = get_default_config()
                self.save_config()
                logger.info("Created default configuration")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self.config = get_default_config()

        return self.config
    
    def save_config(self):
        """保存配置到文件"""
        try:
            # 确保数据目录存在
            DATA_DIR.mkdir(parents=True, exist_ok=True)

            if isinstance(self.config, dict) and self.config.get('_config_version') != CONFIG_VERSION:
                self.config['_config_version'] = CONFIG_VERSION
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key_path: 配置路径，如 "download.default_quality"
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any):
        """
        设置配置值
        
        Args:
            key_path: 配置路径，如 "download.default_quality"
            value: 配置值
        """
        keys = key_path.split('.')
        config = self.config
        
        # 遍历到倒数第二层
        for key in keys[:-1]:
            if key not in config or not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
        
        # 设置最后一层的值
        config[keys[-1]] = value
        self.save_config()
    
    def update(self, updates: Dict[str, Any]):
        """
        批量更新配置
        
        Args:
            updates: 配置更新字典
        """
        self.config = self._merge_config(self.config, updates)
        self.save_config()
    
    def reset(self):
        """重置为默认配置"""
        self.config = get_default_config()
        self.save_config()
        logger.info("Configuration reset to default")
    
    def _merge_config(self, base: Dict, updates: Dict) -> Dict:
        """深度合并配置字典"""
        result = base.copy()
        
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置（深拷贝）"""
        import copy
        return copy.deepcopy(self.config)


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


DEFAULT_CONFIG = get_default_config()
