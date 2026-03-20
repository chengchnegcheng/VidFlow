"""
平台扫码登录注册表

管理所有支持扫码登录的平台Provider。
"""

import logging
from typing import Dict, List, Optional

from .base_provider import PlatformQRProvider

logger = logging.getLogger(__name__)


class PlatformQRRegistry:
    """平台扫码登录注册表

    管理所有平台的QR登录Provider，支持注册、获取和启用/禁用功能。
    """

    def __init__(self):
        self._providers: Dict[str, PlatformQRProvider] = {}
        self._enabled: Dict[str, bool] = {}

    def register(self, provider: PlatformQRProvider, enabled: bool = True) -> None:
        """注册平台Provider

        Args:
            provider: 平台Provider实例
            enabled: 是否启用（默认True）
        """
        platform_id = provider.platform_id
        self._providers[platform_id] = provider
        self._enabled[platform_id] = enabled
        logger.info(f"注册平台Provider: {platform_id} ({provider.platform_name_zh}), enabled={enabled}")

    def unregister(self, platform_id: str) -> bool:
        """注销平台Provider

        Args:
            platform_id: 平台ID

        Returns:
            是否成功注销
        """
        if platform_id in self._providers:
            del self._providers[platform_id]
            del self._enabled[platform_id]
            logger.info(f"注销平台Provider: {platform_id}")
            return True
        return False

    def get_provider(self, platform_id: str) -> Optional[PlatformQRProvider]:
        """获取平台Provider

        只返回已启用的Provider。

        Args:
            platform_id: 平台ID

        Returns:
            平台Provider实例，如果不存在或未启用则返回None
        """
        if not self._enabled.get(platform_id, False):
            return None
        return self._providers.get(platform_id)

    def get_provider_unchecked(self, platform_id: str) -> Optional[PlatformQRProvider]:
        """获取平台Provider（不检查启用状态）

        Args:
            platform_id: 平台ID

        Returns:
            平台Provider实例，如果不存在则返回None
        """
        return self._providers.get(platform_id)

    def get_supported_platforms(self) -> List[Dict]:
        """获取支持扫码登录的平台列表

        Returns:
            平台信息列表，每个元素包含:
            - platform_id: 平台ID
            - platform_name_zh: 平台中文名称
            - qr_expiry_seconds: 二维码过期时间
            - enabled: 是否启用
        """
        return [
            {
                "platform_id": p.platform_id,
                "platform_name_zh": p.platform_name_zh,
                "qr_expiry_seconds": p.qr_expiry_seconds,
                "enabled": self._enabled.get(p.platform_id, False)
            }
            for p in self._providers.values()
        ]

    def get_enabled_platforms(self) -> List[Dict]:
        """获取已启用的平台列表

        Returns:
            已启用的平台信息列表
        """
        return [
            p for p in self.get_supported_platforms()
            if p["enabled"]
        ]

    def set_enabled(self, platform_id: str, enabled: bool) -> bool:
        """启用/禁用平台扫码登录

        Args:
            platform_id: 平台ID
            enabled: 是否启用

        Returns:
            是否成功设置（平台存在则成功）
        """
        if platform_id in self._providers:
            self._enabled[platform_id] = enabled
            logger.info(f"设置平台 {platform_id} enabled={enabled}")
            return True
        return False

    def is_enabled(self, platform_id: str) -> bool:
        """检查平台是否启用

        Args:
            platform_id: 平台ID

        Returns:
            是否启用
        """
        return self._enabled.get(platform_id, False)

    def has_platform(self, platform_id: str) -> bool:
        """检查平台是否已注册

        Args:
            platform_id: 平台ID

        Returns:
            是否已注册
        """
        return platform_id in self._providers

    def get_all_platform_ids(self) -> List[str]:
        """获取所有已注册的平台ID

        Returns:
            平台ID列表
        """
        return list(self._providers.keys())

    def clear(self) -> None:
        """清空所有注册的Provider"""
        self._providers.clear()
        self._enabled.clear()


# 全局注册表单例
_qr_registry: Optional[PlatformQRRegistry] = None


def get_qr_registry() -> PlatformQRRegistry:
    """获取全局QR登录注册表单例

    Returns:
        PlatformQRRegistry实例
    """
    global _qr_registry
    if _qr_registry is None:
        _qr_registry = PlatformQRRegistry()
    return _qr_registry


def reset_qr_registry() -> None:
    """重置全局QR登录注册表（主要用于测试）"""
    global _qr_registry
    if _qr_registry is not None:
        _qr_registry.clear()
    _qr_registry = None
