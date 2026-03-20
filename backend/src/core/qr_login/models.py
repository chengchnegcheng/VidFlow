"""
QR登录相关的数据模型和枚举

定义扫码登录过程中使用的所有数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class QRLoginStatus(str, Enum):
    """扫码登录状态枚举"""
    LOADING = "loading"      # 正在获取二维码
    WAITING = "waiting"      # 等待扫码
    SCANNED = "scanned"      # 已扫码待确认
    SUCCESS = "success"      # 登录成功
    EXPIRED = "expired"      # 二维码已过期
    ERROR = "error"          # 发生错误


@dataclass
class QRCodeResult:
    """二维码生成结果

    Attributes:
        qrcode_url: 二维码内容URL（用于生成二维码图片，可以是URL或base64图片）
        qrcode_key: 二维码唯一标识（用于轮询状态）
        expires_in: 过期时间（秒）
        message: 提示消息
    """
    qrcode_url: str
    qrcode_key: str
    expires_in: int
    message: str


@dataclass
class QRLoginResult:
    """扫码登录结果

    Attributes:
        status: 登录状态
        message: 状态消息（中文）
        cookies: Netscape格式的Cookie字符串（仅在登录成功时有值）
    """
    status: QRLoginStatus
    message: str
    cookies: Optional[str] = None


# ============ Pydantic 响应模型 ============

class QRCodeResponse(BaseModel):
    """二维码响应模型（API响应）"""
    qrcode_url: str
    qrcode_key: str
    expires_in: int
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "qrcode_url": "https://example.com/qr/xxx",
                "qrcode_key": "abc123",
                "expires_in": 180,
                "message": "请使用 哔哩哔哩 APP 扫描二维码登录"
            }
        }
    )


class QRStatusResponse(BaseModel):
    """扫码状态响应模型（API响应）"""
    status: str  # loading, waiting, scanned, success, expired, error
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "waiting",
                "message": "等待扫码..."
            }
        }
    )


class QRSupportedPlatform(BaseModel):
    """支持扫码登录的平台信息"""
    platform_id: str
    platform_name_zh: str
    qr_expiry_seconds: int
    enabled: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "platform_id": "bilibili",
                "platform_name_zh": "哔哩哔哩",
                "qr_expiry_seconds": 180,
                "enabled": True
            }
        }
    )


class QRSupportedPlatformsResponse(BaseModel):
    """支持扫码登录的平台列表响应"""
    platforms: List[QRSupportedPlatform]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "platforms": [
                    {
                        "platform_id": "bilibili",
                        "platform_name_zh": "哔哩哔哩",
                        "qr_expiry_seconds": 180,
                        "enabled": True
                    },
                    {
                        "platform_id": "douyin",
                        "platform_name_zh": "抖音",
                        "qr_expiry_seconds": 180,
                        "enabled": True
                    }
                ]
            }
        }
    )


class QRLoginErrorResponse(BaseModel):
    """扫码登录错误响应"""
    status: str = "error"
    error: str
    error_code: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "error",
                "error": "网络连接超时，请检查网络后重试",
                "error_code": "NETWORK_TIMEOUT"
            }
        }
    )


# ============ 错误代码常量 ============

class QRLoginErrorCode:
    """QR登录错误代码"""
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"           # 网络超时
    API_ERROR = "API_ERROR"                       # API错误
    QR_EXPIRED = "QR_EXPIRED"                     # 二维码过期
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"  # 需要验证
    COOKIE_CONVERSION_FAILED = "COOKIE_CONVERSION_FAILED"  # Cookie转换失败
    PLATFORM_NOT_SUPPORTED = "PLATFORM_NOT_SUPPORTED"  # 平台不支持
    PLATFORM_DISABLED = "PLATFORM_DISABLED"       # 平台已禁用
    NO_QRCODE = "NO_QRCODE"                       # 未获取二维码
    BROWSER_ERROR = "BROWSER_ERROR"               # 浏览器错误
    INTERNAL_ERROR = "INTERNAL_ERROR"             # 内部错误


# ============ 状态消息映射 ============

def get_status_message(status: QRLoginStatus, platform_name_zh: str = "") -> str:
    """获取状态对应的中文消息

    Args:
        status: 登录状态
        platform_name_zh: 平台中文名称

    Returns:
        对应的中文状态消息
    """
    messages = {
        QRLoginStatus.LOADING: "正在获取二维码...",
        QRLoginStatus.WAITING: f"请使用 {platform_name_zh} APP 扫描二维码" if platform_name_zh else "等待扫码...",
        QRLoginStatus.SCANNED: "已扫码，请在手机上确认登录",
        QRLoginStatus.SUCCESS: f"{platform_name_zh} Cookie 获取成功并已保存" if platform_name_zh else "登录成功",
        QRLoginStatus.EXPIRED: "二维码已过期，请重新获取",
        QRLoginStatus.ERROR: "发生错误",
    }
    return messages.get(status, "未知状态")
