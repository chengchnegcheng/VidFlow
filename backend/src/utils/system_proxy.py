#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Windows system proxy helpers for temporary capture-mode overrides."""

from __future__ import annotations

import ctypes
import json
import logging
import socket
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import winreg

logger = logging.getLogger(__name__)


class SystemProxyManager:
    """Manage Windows Internet Settings and restore them after capture."""

    _STATE_KEY = r"Software\VidFlow\SystemProxyManager"
    _STATE_VALUE = "ManagedBackup"
    _LOCAL_BYPASS = (
        "localhost;127.0.0.1;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;"
        "172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;172.26.*;172.27.*;"
        "172.28.*;172.29.*;172.30.*;172.31.*;192.168.*;<local>"
    )

    def __init__(self) -> None:
        self._original_settings: Optional[Dict[str, Any]] = None

    def set_proxy(self, proxy_address: str) -> bool:
        """Enable an explicit system proxy and disable PAC autodiscovery."""
        try:
            self._save_original_settings()
            self._persist_original_settings(mode="explicit_proxy", managed_proxy=proxy_address)
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0,
                winreg.KEY_WRITE,
            ) as internet_settings:
                winreg.SetValueEx(internet_settings, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(internet_settings, "ProxyServer", 0, winreg.REG_SZ, proxy_address)
                winreg.SetValueEx(
                    internet_settings,
                    "ProxyOverride",
                    0,
                    winreg.REG_SZ,
                    self._LOCAL_BYPASS,
                )
                self._set_string_value(internet_settings, "AutoConfigURL", "")
                winreg.SetValueEx(internet_settings, "AutoDetect", 0, winreg.REG_DWORD, 0)

            self._notify_settings_changed()
            logger.info("System proxy set to %s", proxy_address)
            return True
        except Exception as exc:
            logger.error("Failed to set system proxy: %s", exc)
            return False

    def disable_proxy(self) -> bool:
        """Temporarily disable explicit proxy and PAC settings."""
        try:
            self._save_original_settings()
            self._persist_original_settings(mode="transparent_disable", managed_proxy="")
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0,
                winreg.KEY_WRITE,
            ) as internet_settings:
                winreg.SetValueEx(internet_settings, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                self._set_string_value(internet_settings, "ProxyServer", "")
                self._set_string_value(internet_settings, "AutoConfigURL", "")
                winreg.SetValueEx(internet_settings, "AutoDetect", 0, winreg.REG_DWORD, 0)

            self._notify_settings_changed()
            logger.info("Temporarily disabled system proxy/PAC for transparent capture")
            return True
        except Exception as exc:
            logger.error("Failed to disable system proxy/PAC: %s", exc)
            return False

    def restore_proxy(self) -> bool:
        """Restore the settings saved by the last managed override."""
        try:
            settings = self._original_settings
            if settings is None:
                persisted = self._load_persisted_state()
                if persisted:
                    settings = persisted.get("original_settings")
            if settings is None:
                logger.warning("No saved system proxy settings to restore")
                return False

            settings = dict(settings)
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0,
                winreg.KEY_WRITE,
            ) as internet_settings:
                winreg.SetValueEx(
                    internet_settings,
                    "ProxyEnable",
                    0,
                    winreg.REG_DWORD,
                    int(settings.get("ProxyEnable", 0) or 0),
                )
                self._set_string_value(
                    internet_settings,
                    "ProxyServer",
                    str(settings.get("ProxyServer", "") or ""),
                )
                self._set_string_value(
                    internet_settings,
                    "ProxyOverride",
                    str(settings.get("ProxyOverride", "") or ""),
                )
                self._set_string_value(
                    internet_settings,
                    "AutoConfigURL",
                    str(settings.get("AutoConfigURL", "") or ""),
                )
                winreg.SetValueEx(
                    internet_settings,
                    "AutoDetect",
                    0,
                    winreg.REG_DWORD,
                    int(settings.get("AutoDetect", 0) or 0),
                )

            self._notify_settings_changed()
            self._original_settings = None
            self._clear_persisted_state()
            logger.info("System proxy settings restored")
            return True
        except Exception as exc:
            try:
                logger.error("Failed to restore system proxy settings: %s", exc)
            except Exception:
                print(f"[SystemProxy] Failed to restore system proxy settings: {exc}")
            return False

    def has_active_proxy(self) -> bool:
        """Return True when Windows still has proxy or PAC enabled."""
        settings = self._get_current_settings()
        return bool(
            settings.get("ProxyEnable")
            or settings.get("AutoConfigURL")
            or settings.get("AutoDetect")
        )

    def get_current_proxy(self) -> str:
        """Return the active explicit proxy server or PAC URL."""
        settings = self._get_current_settings()
        if settings.get("ProxyEnable") and settings.get("ProxyServer"):
            return str(settings["ProxyServer"])
        if settings.get("AutoConfigURL"):
            return str(settings["AutoConfigURL"])
        return ""

    def _save_original_settings(self) -> None:
        if self._original_settings is None:
            self._original_settings = self._get_current_settings()

    def has_persisted_state(self) -> bool:
        return self._load_persisted_state() is not None

    def discard_persisted_state(self) -> None:
        self._clear_persisted_state()

    def is_current_settings_managed(self) -> bool:
        payload = self._load_persisted_state()
        if not payload:
            return False

        settings = self._get_current_settings()
        mode = str(payload.get("mode") or "")
        managed_proxy = str(payload.get("managed_proxy") or "")

        if mode == "explicit_proxy":
            return (
                int(settings.get("ProxyEnable", 0) or 0) == 1
                and str(settings.get("ProxyServer") or "") == managed_proxy
                and str(settings.get("ProxyOverride") or "") == self._LOCAL_BYPASS
                and not str(settings.get("AutoConfigURL") or "")
                and int(settings.get("AutoDetect", 0) or 0) == 0
            )

        if mode == "transparent_disable":
            return (
                int(settings.get("ProxyEnable", 0) or 0) == 0
                and not str(settings.get("ProxyServer") or "")
                and not str(settings.get("AutoConfigURL") or "")
                and int(settings.get("AutoDetect", 0) or 0) == 0
            )

        return False

    def cleanup_stale_managed_proxy(self) -> bool:
        """Clear a dead localhost proxy left behind by older VidFlow runs."""
        settings = self._get_current_settings()
        proxy_enabled = int(settings.get("ProxyEnable", 0) or 0) == 1
        proxy_server = str(settings.get("ProxyServer") or "")
        proxy_override = str(settings.get("ProxyOverride") or "")
        auto_config_url = str(settings.get("AutoConfigURL") or "")

        if auto_config_url:
            pac_server = self._parse_local_proxy_url(auto_config_url)
            if pac_server and not self._is_local_proxy_server_reachable(pac_server):
                self._clear_proxy_and_pac_only()
                logger.warning(
                    "Cleared stale localhost PAC %s because no local listener was reachable",
                    auto_config_url,
                )
                return True
            return False

        if not proxy_enabled or not proxy_server:
            return False
        if proxy_override != self._LOCAL_BYPASS:
            return False
        if not self._parse_local_proxy_server(proxy_server):
            return False
        if self._is_local_proxy_server_reachable(proxy_server):
            return False

        self._clear_explicit_proxy_only()
        logger.warning(
            "Cleared stale VidFlow-managed system proxy %s because no local listener was reachable",
            proxy_server,
        )
        return True

    def _get_current_settings(self) -> Dict[str, Any]:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0,
                winreg.KEY_READ,
            ) as internet_settings:
                return {
                    "ProxyEnable": self._query_value(internet_settings, "ProxyEnable", 0),
                    "ProxyServer": self._query_value(internet_settings, "ProxyServer", ""),
                    "ProxyOverride": self._query_value(internet_settings, "ProxyOverride", ""),
                    "AutoConfigURL": self._query_value(internet_settings, "AutoConfigURL", ""),
                    "AutoDetect": self._query_value(internet_settings, "AutoDetect", 0),
                }
        except Exception as exc:
            logger.error("Failed to read current system proxy settings: %s", exc)
            return {
                "ProxyEnable": 0,
                "ProxyServer": "",
                "ProxyOverride": "",
                "AutoConfigURL": "",
                "AutoDetect": 0,
            }

    @staticmethod
    def _query_value(key: Any, name: str, default: Any) -> Any:
        try:
            value, _ = winreg.QueryValueEx(key, name)
            return value
        except FileNotFoundError:
            return default

    def _persist_original_settings(self, mode: str, managed_proxy: str) -> None:
        if self._original_settings is None:
            return

        payload = {
            "mode": str(mode or ""),
            "managed_proxy": str(managed_proxy or ""),
            "original_settings": dict(self._original_settings),
        }
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self._STATE_KEY) as key:
                winreg.SetValueEx(key, self._STATE_VALUE, 0, winreg.REG_SZ, json.dumps(payload))
        except Exception as exc:
            logger.warning("Failed to persist system proxy backup: %s", exc)

    def _load_persisted_state(self) -> Optional[Dict[str, Any]]:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self._STATE_KEY,
                0,
                winreg.KEY_READ,
            ) as key:
                raw, _ = winreg.QueryValueEx(key, self._STATE_VALUE)
        except FileNotFoundError:
            return None
        except Exception as exc:
            logger.warning("Failed to read persisted system proxy backup: %s", exc)
            return None

        try:
            payload = json.loads(str(raw or ""))
        except Exception as exc:
            logger.warning("Failed to parse persisted system proxy backup: %s", exc)
            return None

        if not isinstance(payload, dict):
            return None
        if not isinstance(payload.get("original_settings"), dict):
            return None
        return payload

    def _clear_persisted_state(self) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self._STATE_KEY,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, self._STATE_VALUE)
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.warning("Failed to clear persisted system proxy backup: %s", exc)

    def _clear_explicit_proxy_only(self) -> None:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_WRITE,
        ) as internet_settings:
            winreg.SetValueEx(internet_settings, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            self._set_string_value(internet_settings, "ProxyServer", "")
            self._set_string_value(internet_settings, "ProxyOverride", "")

        self._notify_settings_changed()

    @staticmethod
    def _clear_proxy_and_pac_only() -> None:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_WRITE,
        ) as internet_settings:
            winreg.SetValueEx(internet_settings, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            SystemProxyManager._set_string_value(internet_settings, "ProxyServer", "")
            SystemProxyManager._set_string_value(internet_settings, "ProxyOverride", "")
            SystemProxyManager._set_string_value(internet_settings, "AutoConfigURL", "")
            winreg.SetValueEx(internet_settings, "AutoDetect", 0, winreg.REG_DWORD, 0)

        SystemProxyManager._notify_settings_changed()

    @staticmethod
    def _parse_local_proxy_server(proxy_server: str) -> Optional[tuple[str, int]]:
        candidate = str(proxy_server or "").strip()
        if not candidate:
            return None

        first_entry = candidate.split(";", 1)[0].strip()
        if "=" in first_entry:
            first_entry = first_entry.split("=", 1)[1].strip()

        host, sep, port_text = first_entry.rpartition(":")
        if not sep:
            return None

        host = host.strip().strip("[]").lower()
        if host not in {"127.0.0.1", "localhost"}:
            return None

        try:
            port = int(port_text)
        except (TypeError, ValueError):
            return None

        if port <= 0 or port > 65535:
            return None

        return host, port

    @staticmethod
    def _parse_local_proxy_url(auto_config_url: str) -> Optional[str]:
        candidate = str(auto_config_url or "").strip()
        if not candidate:
            return None

        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None

        if not parsed.hostname or parsed.hostname.lower() not in {"127.0.0.1", "localhost"}:
            return None

        if parsed.port is None:
            return None

        return f"{parsed.hostname}:{parsed.port}"

    def _is_local_proxy_server_reachable(self, proxy_server: str) -> bool:
        parsed = self._parse_local_proxy_server(proxy_server)
        if not parsed:
            return False

        host, port = parsed
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            return False

    @staticmethod
    def _set_string_value(key: Any, name: str, value: str) -> None:
        if value:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            return
        try:
            winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass

    @staticmethod
    def _notify_settings_changed() -> None:
        internet_set_option = ctypes.windll.Wininet.InternetSetOptionW
        internet_set_option(0, 39, 0, 0)
        internet_set_option(0, 37, 0, 0)
