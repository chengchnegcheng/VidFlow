import sys
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

if sys.platform == "win32":
    from src.utils.system_proxy import SystemProxyManager


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
class TestSystemProxyManager:
    def test_cleanup_stale_managed_proxy_clears_dead_localhost_proxy(self):
        manager = SystemProxyManager()

        stale_settings = {
            "ProxyEnable": 1,
            "ProxyServer": "127.0.0.1:4751",
            "ProxyOverride": manager._LOCAL_BYPASS,
            "AutoConfigURL": "",
            "AutoDetect": 0,
        }

        with patch.object(manager, "_get_current_settings", return_value=stale_settings), patch.object(
            manager,
            "_is_local_proxy_server_reachable",
            return_value=False,
        ), patch.object(manager, "_clear_explicit_proxy_only") as clear_proxy:
            assert manager.cleanup_stale_managed_proxy() is True

        clear_proxy.assert_called_once()

    def test_cleanup_stale_managed_proxy_clears_dead_localhost_pac(self):
        manager = SystemProxyManager()

        stale_settings = {
            "ProxyEnable": 0,
            "ProxyServer": "127.0.0.1:8888",
            "ProxyOverride": manager._LOCAL_BYPASS,
            "AutoConfigURL": "http://127.0.0.1:33331/commands/pac",
            "AutoDetect": 0,
        }

        with patch.object(manager, "_get_current_settings", return_value=stale_settings), patch.object(
            manager,
            "_is_local_proxy_server_reachable",
            return_value=False,
        ), patch.object(manager, "_clear_proxy_and_pac_only") as clear_proxy:
            assert manager.cleanup_stale_managed_proxy() is True

        clear_proxy.assert_called_once()

    def test_cleanup_stale_managed_proxy_preserves_active_or_non_vidflow_proxy(self):
        manager = SystemProxyManager()

        active_settings = {
            "ProxyEnable": 1,
            "ProxyServer": "127.0.0.1:7890",
            "ProxyOverride": "localhost;<local>",
            "AutoConfigURL": "",
            "AutoDetect": 0,
        }

        with patch.object(manager, "_get_current_settings", return_value=active_settings), patch.object(
            manager,
            "_clear_explicit_proxy_only",
        ) as clear_proxy:
            assert manager.cleanup_stale_managed_proxy() is False

        clear_proxy.assert_not_called()
