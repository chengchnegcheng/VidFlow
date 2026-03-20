"""
代理软件检测器

检测系统中运行的代理软件及其工作模式。
支持 Clash、Surge、V2Ray、Shadowsocks 等常见代理软件。
"""

import asyncio
import json
import logging
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import aiohttp

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import winreg

    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .models import ProxyInfo, ProxyMode, ProxyType

logger = logging.getLogger(__name__)


class ProxyDetector:
    """代理软件检测器。"""

    PROXY_PROCESSES: Dict[ProxyType, List[str]] = {
        ProxyType.CLASH: [
            "clash.exe",
            "clash-windows.exe",
            "clash-win64.exe",
            "clash-linux",
            "clash-darwin",
            "clash",
        ],
        ProxyType.CLASH_VERGE: [
            "clash-verge.exe",
            "verge-mihomo.exe",
            "clash verge.exe",
            "clash-verge-service.exe",
            "clash-nyanpasu.exe",
        ],
        ProxyType.CLASH_META: [
            "mihomo.exe",
            "clash-meta.exe",
            "mihomo-windows.exe",
            "mihomo-linux",
            "mihomo-darwin",
            "mihomo",
        ],
        ProxyType.SURGE: ["surge.exe", "surge-cli.exe"],
        ProxyType.V2RAY: [
            "v2ray.exe",
            "v2rayn.exe",
            "v2rayn-core.exe",
            "xray.exe",
            "v2ray-core.exe",
            "v2ray",
            "xray",
        ],
        ProxyType.SHADOWSOCKS: [
            "shadowsocks.exe",
            "ss-local.exe",
            "sslocal.exe",
            "shadowsocks-rust.exe",
            "shadowsocks-libev.exe",
            "ss-local",
            "sslocal",
        ],
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

    TUN_INTERFACE_KEYWORDS = (
        "tun",
        "wintun",
        "clash",
        "mihomo",
        "meta",
        "surge",
        "v2ray",
        "xray",
        "warp",
    )

    def __init__(self) -> None:
        self._cached_proxy_info: Optional[ProxyInfo] = None

    @staticmethod
    def _normalize_process_name(process_name: Optional[str]) -> str:
        return Path(str(process_name or "").strip()).name.lower()

    @classmethod
    def get_proxy_type_from_process_name(cls, process_name: Optional[str]) -> ProxyType:
        normalized = cls._normalize_process_name(process_name)
        if not normalized:
            return ProxyType.NONE

        for proxy_type, process_names in cls.PROXY_PROCESSES.items():
            if normalized in {name.lower() for name in process_names}:
                return proxy_type
        return ProxyType.NONE

    @staticmethod
    def is_clash_type(proxy_type: ProxyType) -> bool:
        return proxy_type in {
            ProxyType.CLASH,
            ProxyType.CLASH_VERGE,
            ProxyType.CLASH_META,
        }

    def get_cached_info(self) -> Optional[ProxyInfo]:
        return self._cached_proxy_info

    def clear_cache(self) -> None:
        self._cached_proxy_info = None

    def _scan_proxy_processes(self) -> Tuple[ProxyType, Optional[str], Optional[int]]:
        if not HAS_PSUTIL:
            return ProxyType.NONE, None, None

        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    process_name = proc.info.get("name")
                    proxy_type = self.get_proxy_type_from_process_name(process_name)
                    if proxy_type == ProxyType.NONE:
                        continue
                    return proxy_type, process_name, proc.info.get("pid")
                except Exception:
                    logger.debug("Failed to inspect proxy process", exc_info=True)
        except Exception:
            logger.debug("Failed to iterate processes", exc_info=True)

        return ProxyType.NONE, None, None

    def _is_system_proxy_enabled(self) -> bool:
        if not HAS_WINREG:
            return False

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0,
                winreg.KEY_READ,
            ) as key:
                try:
                    enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
                except FileNotFoundError:
                    enabled = 0

                try:
                    auto_config_url, _ = winreg.QueryValueEx(key, "AutoConfigURL")
                except FileNotFoundError:
                    auto_config_url = ""

                try:
                    auto_detect, _ = winreg.QueryValueEx(key, "AutoDetect")
                except FileNotFoundError:
                    auto_detect = 0

                return bool(enabled or str(auto_config_url or "").strip() or auto_detect)
        except FileNotFoundError:
            return False
        except Exception:
            logger.debug("Failed to detect system proxy", exc_info=True)
            return False

    def _is_tun_mode_enabled(self) -> bool:
        if not HAS_PSUTIL:
            return False

        try:
            interfaces = psutil.net_if_addrs()
        except Exception:
            logger.debug("Failed to inspect network interfaces", exc_info=True)
            return False

        for name in interfaces.keys():
            normalized = str(name or "").lower()
            if any(keyword in normalized for keyword in self.TUN_INTERFACE_KEYWORDS):
                return True
        return False

    def _read_clash_config(self) -> Optional[Dict[str, Any]]:
        if not HAS_YAML:
            return None

        for config_path in self.CLASH_CONFIG_PATHS:
            try:
                if not config_path.exists() or not config_path.is_file():
                    continue
                with config_path.open("r", encoding="utf-8") as fp:
                    data = yaml.safe_load(fp) or {}
                if isinstance(data, dict):
                    return data
            except Exception:
                logger.debug("Failed to read clash config: %s", config_path, exc_info=True)
        return None

    def _is_fake_ip_enabled(self) -> bool:
        config = self._read_clash_config()
        if isinstance(config, dict):
            dns_config = config.get("dns")
            if isinstance(dns_config, dict):
                enhanced_mode = str(dns_config.get("enhanced-mode", "")).strip().lower()
                if enhanced_mode == "fake-ip":
                    return True

        try:
            resolved_ip = socket.gethostbyname("dns.google")
            return resolved_ip.startswith("198.18.") or resolved_ip.startswith("198.19.")
        except Exception:
            logger.debug("Failed to detect fake-ip mode via DNS", exc_info=True)
            return False

    async def detect_proxy_mode(self, proxy_type: ProxyType) -> ProxyMode:
        if self._is_system_proxy_enabled():
            return ProxyMode.SYSTEM_PROXY
        if self._is_tun_mode_enabled():
            return ProxyMode.TUN
        if self.is_clash_type(proxy_type) and self._is_fake_ip_enabled():
            return ProxyMode.FAKE_IP
        return ProxyMode.RULE

    @staticmethod
    def _normalize_api_address(value: Optional[str]) -> Optional[str]:
        address = str(value or "").strip()
        if not address:
            return None
        if address.startswith(("http://", "https://")):
            address = address.split("://", 1)[1]
        if "/" in address:
            address = address.split("/", 1)[0]
        return address or None

    async def get_clash_api_info(self) -> Tuple[Optional[str], Optional[str]]:
        config = self._read_clash_config()
        if isinstance(config, dict):
            api_address = self._normalize_api_address(config.get("external-controller"))
            api_secret = str(config.get("secret") or "").strip() or None
            if api_address:
                return api_address, api_secret

        if not HAS_AIOHTTP:
            return None, None

        timeout = aiohttp.ClientTimeout(total=1)
        for port in self.CLASH_DEFAULT_API_PORTS:
            base_url = f"http://127.0.0.1:{port}"
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(f"{base_url}/version") as resp:
                        if resp.status == 200:
                            return f"127.0.0.1:{port}", None
            except Exception:
                continue

        return None, None

    async def detect(self) -> ProxyInfo:
        if not HAS_PSUTIL:
            logger.warning("psutil not available")
            return ProxyInfo(proxy_type=ProxyType.NONE, proxy_mode=ProxyMode.NONE)

        proxy_type, process_name, process_pid = self._scan_proxy_processes()
        if proxy_type == ProxyType.NONE:
            return ProxyInfo(proxy_type=ProxyType.NONE, proxy_mode=ProxyMode.NONE)

        proxy_mode = await self.detect_proxy_mode(proxy_type)
        api_address, api_secret = None, None
        if self.is_clash_type(proxy_type):
            api_address, api_secret = await self.get_clash_api_info()

        proxy_info = ProxyInfo(
            proxy_type=proxy_type,
            proxy_mode=proxy_mode,
            process_name=process_name,
            process_pid=process_pid,
            api_address=api_address,
            api_secret=api_secret,
            is_tun_enabled=self._is_tun_mode_enabled(),
            is_fake_ip_enabled=self._is_fake_ip_enabled(),
        )
        self._cached_proxy_info = proxy_info
        return proxy_info
