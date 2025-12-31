"""
代理配置辅助模块
从配置管理器读取代理设置，或自动检测系统代理，供下载器使用
"""
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_system_proxy() -> Optional[str]:
    """
    获取系统环境变量中的代理设置
    
    Returns:
        代理 URL 字符串，如果没有设置则返回 None
    """
    # 优先使用 HTTPS 代理，其次 HTTP 代理
    proxy_url = (
        os.environ.get('HTTPS_PROXY') or 
        os.environ.get('https_proxy') or
        os.environ.get('HTTP_PROXY') or 
        os.environ.get('http_proxy') or
        os.environ.get('ALL_PROXY') or
        os.environ.get('all_proxy')
    )
    
    if proxy_url:
        logger.debug(f"Detected system proxy: {proxy_url}")
    
    return proxy_url


def get_proxy_url() -> Optional[str]:
    """
    获取代理 URL（优先使用配置，其次使用系统代理）
    
    Returns:
        代理 URL 字符串，如 "http://127.0.0.1:7890"
        如果代理未启用或配置无效，返回 None
    """
    try:
        from src.core.config_manager import get_config_manager
        config = get_config_manager()
        
        # 读取代理配置
        proxy_enabled = config.get('advanced.proxy.enabled', False)
        
        if proxy_enabled:
            proxy_type = config.get('advanced.proxy.type', 'http')
            proxy_host = config.get('advanced.proxy.host', '')
            proxy_port = config.get('advanced.proxy.port', 0)
            proxy_username = config.get('advanced.proxy.username', '')
            proxy_password = config.get('advanced.proxy.password', '')
            
            # 验证必要配置
            if proxy_host and proxy_port:
                # 构建代理 URL
                if proxy_username and proxy_password:
                    proxy_url = f"{proxy_type}://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
                else:
                    proxy_url = f"{proxy_type}://{proxy_host}:{proxy_port}"
                
                logger.debug(f"Using configured proxy: {proxy_type}://{proxy_host}:{proxy_port}")
                return proxy_url
            else:
                logger.warning("Proxy enabled but host/port not configured, falling back to system proxy")
        
        # 配置未启用或无效，尝试使用系统代理
        system_proxy = get_system_proxy()
        if system_proxy:
            logger.debug(f"Using system proxy: {system_proxy}")
            return system_proxy
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to get proxy config: {e}, trying system proxy")
        return get_system_proxy()


def get_ydl_proxy_opts() -> Dict[str, Any]:
    """
    获取 yt-dlp 的代理配置选项
    
    Returns:
        包含代理配置的字典，可直接合并到 ydl_opts
    """
    proxy_url = get_proxy_url()
    if proxy_url:
        return {'proxy': proxy_url}
    return {}


def is_proxy_enabled() -> bool:
    """
    检查代理是否可用（配置启用或系统代理存在）
    
    Returns:
        代理是否可用
    """
    return get_proxy_url() is not None
