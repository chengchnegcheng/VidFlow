"""
QR登录服务

提供统一的扫码登录服务接口。
"""

import time
import logging
from typing import Dict, Optional

from .models import QRCodeResult, QRLoginResult, QRLoginStatus, QRLoginErrorCode
from .registry import PlatformQRRegistry, get_qr_registry

logger = logging.getLogger(__name__)


class QRLoginService:
    """扫码登录服务
    
    提供统一的扫码登录接口，管理二维码缓存和状态轮询。
    """
    
    def __init__(self, registry: Optional[PlatformQRRegistry] = None):
        """初始化服务
        
        Args:
            registry: 平台注册表，如果不提供则使用全局单例
        """
        self.registry = registry or get_qr_registry()
        # 二维码缓存: platform_id -> {key, time, expires_in}
        self._qrcode_cache: Dict[str, Dict] = {}
    
    async def get_qrcode(self, platform_id: str) -> QRCodeResult:
        """获取平台登录二维码
        
        Args:
            platform_id: 平台ID
            
        Returns:
            QRCodeResult: 二维码生成结果
            
        Raises:
            ValueError: 平台不支持或未启用
            Exception: 生成二维码失败
        """
        provider = self.registry.get_provider(platform_id)
        if not provider:
            if self.registry.has_platform(platform_id):
                raise ValueError(f"平台 {platform_id} 扫码登录已禁用")
            raise ValueError(f"平台 {platform_id} 不支持扫码登录")
        
        try:
            result = await provider.generate_qrcode()
            
            # 缓存二维码信息
            self._qrcode_cache[platform_id] = {
                "key": result.qrcode_key,
                "time": time.time(),
                "expires_in": result.expires_in
            }
            
            logger.info(f"生成 {platform_id} 二维码成功, key={result.qrcode_key[:20]}...")
            return result
            
        except Exception as e:
            logger.error(f"生成 {platform_id} 二维码失败: {e}")
            raise
    
    async def check_status(self, platform_id: str) -> QRLoginResult:
        """检查扫码状态
        
        Args:
            platform_id: 平台ID
            
        Returns:
            QRLoginResult: 扫码状态结果
        """
        provider = self.registry.get_provider(platform_id)
        if not provider:
            if self.registry.has_platform(platform_id):
                return QRLoginResult(
                    status=QRLoginStatus.ERROR,
                    message=f"平台 {platform_id} 扫码登录已禁用"
                )
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"平台 {platform_id} 不支持扫码登录"
            )
        
        cache = self._qrcode_cache.get(platform_id)
        if not cache:
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message="请先获取二维码"
            )
        
        # 检查是否超时
        elapsed = time.time() - cache["time"]
        if elapsed > cache["expires_in"]:
            # 清除过期缓存
            del self._qrcode_cache[platform_id]
            return QRLoginResult(
                status=QRLoginStatus.EXPIRED,
                message="二维码已过期，请重新获取"
            )
        
        try:
            result = await provider.check_login_status(cache["key"])
            
            # 登录成功，清除缓存
            if result.status == QRLoginStatus.SUCCESS:
                del self._qrcode_cache[platform_id]
                logger.info(f"{platform_id} 扫码登录成功")
            
            return result
            
        except Exception as e:
            logger.error(f"检查 {platform_id} 扫码状态失败: {e}")
            return QRLoginResult(
                status=QRLoginStatus.ERROR,
                message=f"检查状态失败: {str(e)}"
            )
    
    def get_cached_qrcode_key(self, platform_id: str) -> Optional[str]:
        """获取缓存的二维码key
        
        Args:
            platform_id: 平台ID
            
        Returns:
            二维码key，如果不存在或已过期则返回None
        """
        cache = self._qrcode_cache.get(platform_id)
        if not cache:
            return None
        
        elapsed = time.time() - cache["time"]
        if elapsed > cache["expires_in"]:
            del self._qrcode_cache[platform_id]
            return None
        
        return cache["key"]
    
    def clear_cache(self, platform_id: Optional[str] = None) -> None:
        """清除二维码缓存
        
        Args:
            platform_id: 平台ID，如果不提供则清除所有缓存
        """
        if platform_id:
            if platform_id in self._qrcode_cache:
                del self._qrcode_cache[platform_id]
        else:
            self._qrcode_cache.clear()
    
    async def cancel_login(self, platform_id: str) -> None:
        """取消登录并清理资源
        
        Args:
            platform_id: 平台ID
        """
        # 清除缓存
        self.clear_cache(platform_id)
        
        # 清理Provider资源
        provider = self.registry.get_provider_unchecked(platform_id)
        if provider:
            await provider.cleanup()


# 全局服务单例
_qr_login_service: Optional[QRLoginService] = None


def get_qr_login_service() -> QRLoginService:
    """获取全局QR登录服务单例
    
    Returns:
        QRLoginService实例
    """
    global _qr_login_service
    if _qr_login_service is None:
        _qr_login_service = QRLoginService()
    return _qr_login_service


def reset_qr_login_service() -> None:
    """重置全局QR登录服务（主要用于测试）"""
    global _qr_login_service
    _qr_login_service = None
