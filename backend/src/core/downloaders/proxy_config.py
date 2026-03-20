"""
代理配置辅助模块
从配置管理器读取代理设置，或自动检测系统代理，供下载器使用
"""
import os
import sys
import logging
import subprocess
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# 全局标志：是否临时禁用代理
_proxy_disabled = False


def disable_proxy_temporarily():
    """临时禁用代理（用于绕过 bot 检测）"""
    global _proxy_disabled
    _proxy_disabled = True
    logger.info("[Proxy] Proxy temporarily disabled")


def enable_proxy():
    """重新启用代理"""
    global _proxy_disabled
    _proxy_disabled = False
    logger.info("[Proxy] Proxy re-enabled")


def is_proxy_disabled() -> bool:
    """检查代理是否被临时禁用"""
    return _proxy_disabled


def get_macos_system_proxy() -> Optional[str]:
    """
    获取 macOS 系统代理设置（通过 scutil 命令）

    Returns:
        代理 URL 字符串，如果没有设置则返回 None
    """
    if sys.platform != 'darwin':
        return None

    try:
        # 使用 scutil 获取系统代理设置
        result = subprocess.run(
            ['scutil', '--proxy'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return None

        output = result.stdout

        # 解析 HTTP 代理
        http_enabled = False
        http_host = None
        http_port = None

        # 解析 SOCKS 代理
        socks_enabled = False
        socks_host = None
        socks_port = None

        for line in output.split('\n'):
            line = line.strip()
            if 'HTTPEnable' in line and ': 1' in line:
                http_enabled = True
            elif 'HTTPProxy' in line and ':' in line:
                http_host = line.split(':')[-1].strip()
            elif 'HTTPPort' in line and ':' in line:
                http_port = line.split(':')[-1].strip()
            elif 'SOCKSEnable' in line and ': 1' in line:
                socks_enabled = True
            elif 'SOCKSProxy' in line and ':' in line:
                socks_host = line.split(':')[-1].strip()
            elif 'SOCKSPort' in line and ':' in line:
                socks_port = line.split(':')[-1].strip()

        # 优先使用 HTTP 代理
        if http_enabled and http_host and http_port:
            proxy_url = f"http://{http_host}:{http_port}"
            logger.info(f"[Proxy] Detected macOS HTTP proxy: {proxy_url}")
            return proxy_url

        # 其次使用 SOCKS 代理
        if socks_enabled and socks_host and socks_port:
            proxy_url = f"socks5://{socks_host}:{socks_port}"
            logger.info(f"[Proxy] Detected macOS SOCKS proxy: {proxy_url}")
            return proxy_url

        return None

    except Exception as e:
        logger.debug(f"Failed to get macOS system proxy: {e}")
        return None


def get_system_proxy() -> Optional[str]:
    """
    获取系统代理设置（环境变量或系统设置）

    Returns:
        代理 URL 字符串，如果没有设置则返回 None
    """
    # 优先使用环境变量
    proxy_url = (
        os.environ.get('HTTPS_PROXY') or
        os.environ.get('https_proxy') or
        os.environ.get('HTTP_PROXY') or
        os.environ.get('http_proxy') or
        os.environ.get('ALL_PROXY') or
        os.environ.get('all_proxy')
    )

    if proxy_url:
        logger.debug(f"Detected proxy from environment: {proxy_url}")
        return proxy_url

    # macOS: 尝试从系统设置获取
    if sys.platform == 'darwin':
        macos_proxy = get_macos_system_proxy()
        if macos_proxy:
            return macos_proxy

    return None


def get_proxy_url() -> Optional[str]:
    """
    获取代理 URL（优先使用配置，其次使用系统代理）

    Returns:
        代理 URL 字符串，如 "http://127.0.0.1:7890"
        如果代理未启用或配置无效，返回 None
    """
    # 检查是否临时禁用代理
    if _proxy_disabled:
        logger.debug("[Proxy] Proxy is temporarily disabled, returning None")
        return None

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
