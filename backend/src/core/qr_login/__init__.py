"""
多平台扫码登录模块

提供统一的扫码登录接口，支持多个国内视频平台的扫码登录获取Cookie。
"""

from .models import (
    QRLoginStatus,
    QRCodeResult,
    QRLoginResult,
)
from .base_provider import PlatformQRProvider
from .registry import PlatformQRRegistry, get_qr_registry
from .service import QRLoginService, get_qr_login_service
from .providers import (
    BilibiliQRProvider,
    KuaishouQRProvider,
    WeiboQRProvider,
    IqiyiQRProvider,
    MangoQRProvider,
    TencentQRProvider,
    DouyinQRProvider,
    XiaohongshuQRProvider,
    YoukuQRProvider,
)

__all__ = [
    # 数据模型
    'QRLoginStatus',
    'QRCodeResult',
    'QRLoginResult',
    # 基类
    'PlatformQRProvider',
    # 注册表
    'PlatformQRRegistry',
    'get_qr_registry',
    # 服务
    'QRLoginService',
    'get_qr_login_service',
    # Providers
    'BilibiliQRProvider',
    'KuaishouQRProvider',
    'WeiboQRProvider',
    'IqiyiQRProvider',
    'MangoQRProvider',
    'TencentQRProvider',
    'DouyinQRProvider',
    'XiaohongshuQRProvider',
    'YoukuQRProvider',
]


def register_default_providers() -> None:
    """注册默认的平台Provider
    
    在应用启动时调用此函数来注册所有支持的平台。
    """
    registry = get_qr_registry()
    
    # 标准API平台（默认启用）
    registry.register(BilibiliQRProvider(), enabled=True)
    registry.register(KuaishouQRProvider(), enabled=True)
    registry.register(WeiboQRProvider(), enabled=True)
    registry.register(IqiyiQRProvider(), enabled=True)
    registry.register(MangoQRProvider(), enabled=True)
    registry.register(TencentQRProvider(), enabled=True)
    
    # Playwright平台（默认启用，但需要Playwright依赖）
    registry.register(DouyinQRProvider(), enabled=True)
    registry.register(XiaohongshuQRProvider(), enabled=True)
    registry.register(YoukuQRProvider(), enabled=True)
