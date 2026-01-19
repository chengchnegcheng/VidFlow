"""
代理软件检测器

检测系统中运行的代理软件及其工作模式。
支持 Clash、Surge、V2Ray、Shadowsocks 等常见代理软件。

Validates: Requirements 1.1, 1.2, 1.4, 1.5, 1.6
"""

import os
import re
import json
import logging
import socket
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .models import ProxyType, ProxyMode, ProxyInfo

logger = logging.getLogger(__name__)


class ProxyDetector:
    """代理软件检测器"""
    
    PROXY_PROCESSES: Dict[ProxyType, List[str]] = {
        ProxyType.CLASH: ["clash.exe", "clash-windows.exe", "clash-win64.exe", "clash-linux", "clash-darwin", "clash"],
        ProxyType.CLASH_VERGE: ["clash-verge.exe", "verge-mihomo.exe", "Clash Verge.exe", "clash-verge-service.exe", "clash-nyanpasu.exe"],
        ProxyType.CLASH_META: ["mihomo.exe", "clash-meta.exe", "mihomo-windows.exe", "mihomo-linux", "mihomo-darwin", "mihomo"],
        ProxyType.SURGE: ["surge.exe", "Surge.exe", "surge-cli.exe"],
        ProxyType.V2RAY: ["v2ray.exe", "v2rayN.exe", "v2rayN-Core.exe", "xray.exe", "v2ray-core.exe", "v2ray", "xray"],
        ProxyType.SHADOWSOCKS: ["shadowsocks.exe", "ss-local.exe", "sslocal.exe", "shadowsocks-rust.exe", "shadowsocks-libev.exe", "ss-local", "sslocal"],
    }
    
    CLASH_DEFAULT_API_PORTS = [9090, 9091, 9097, 7890, 7891]
    
    CLASH_CONFIG_PATHS = [
        Path.home() / ".config" / "clash" / "config.yaml",
        Path.home() / ".config" / "clash" / "config.yml",
        Path.home() / ".config" / "clash-verge" / "config.yaml",
        Path.home() / "AppData" / "Roaming" / "io.github.clash-verge-rev.clash-verge-rev" / "config.yaml",
        Path.home() / "AppData" / "Roaming" / "clash-verge" / "config.yaml",
        Path.home() / ".config" / "mihomo" / "config.yaml",
        Path.home() / "AppData" / "Roaming" / "mihomo" / "config.yaml",
        Path("C:/") / "ProgramData" / "clash" / "config.yaml",
    ]
    
    def __init__(self):
        self._cached_proxy_info: Optional[ProxyInfo] = None
        self._process_cache: Dict[int, str] = {}

    async def detect(self) -> ProxyInfo:
        if not HAS_PSUTIL:
            logger.warning("psutil not available")
            return ProxyInfo(proxy_type=ProxyType.NONE, proxy_mode=ProxyMode.NONE)
        proxy_type, process_name, process_pid = self._scan_proxy_processes()
        if proxy_type == ProxyType.NONE:
            return ProxyInfo(proxy_type=ProxyType.NONE, proxy_mode=ProxyMode.NONE)
        proxy_mode = await self.detect_proxy_mode(proxy_type)
        api_address, api_secret = None, None
        if proxy_type in (ProxyType.CLASH, ProxyType.CLASH_VERGE, ProxyType.CLASH_META):
            api_address, api_secret = await self.get_clash_api_info()
        is_tun = self._is_tun_mode_enabled()
        is_fake_ip = self._is_fake_ip_enabled()
        proxy_info = ProxyInfo(
            proxy_type=proxy_type, proxy_mode=proxy_mode, process_name=process_name,
            process_pid=process_pid, api_address=api_address, api_secret=api_secret,
            is_tun_enabled=is_tun, is_fake_ip_enabled=is_fake_ip,
        )
        self._cached_proxy_info = proxy_info
        return proxy_info
