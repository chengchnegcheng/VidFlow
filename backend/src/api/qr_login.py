"""
QR登录 API

提供多平台扫码登录的API端点。
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from src.core.qr_login.models import (
    QRCodeResponse,
    QRStatusResponse,
    QRSupportedPlatformsResponse,
    QRSupportedPlatform,
    QRLoginErrorResponse,
    QRLoginStatus,
    QRLoginErrorCode,
)
from src.core.qr_login.service import get_qr_login_service
from src.core.qr_login.registry import get_qr_registry
from src.core.cookie_storage import write_cookie_file, validate_netscape_cookie_format

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/cookies/qr", tags=["qr-login"])


# ============ 错误消息映射 ============

ERROR_MESSAGES = {
    QRLoginErrorCode.NETWORK_TIMEOUT: "网络连接超时，请检查网络后重试",
    QRLoginErrorCode.API_ERROR: "获取二维码失败，请稍后重试",
    QRLoginErrorCode.QR_EXPIRED: "二维码已过期，请重新获取",
    QRLoginErrorCode.VERIFICATION_REQUIRED: "需要手动验证，请稍后重试",
    QRLoginErrorCode.COOKIE_CONVERSION_FAILED: "Cookie 转换失败，请重试",
    QRLoginErrorCode.PLATFORM_NOT_SUPPORTED: "该平台暂不支持扫码登录",
    QRLoginErrorCode.PLATFORM_DISABLED: "该平台扫码登录已禁用",
    QRLoginErrorCode.NO_QRCODE: "请先获取二维码",
    QRLoginErrorCode.BROWSER_ERROR: "浏览器启动失败，请检查Playwright是否已安装",
    QRLoginErrorCode.INTERNAL_ERROR: "服务器内部错误，请稍后重试",
}


def get_error_message(error_code: str, default: Optional[str] = None) -> str:
    """获取错误代码对应的中文消息

    Args:
        error_code: 错误代码
        default: 默认消息（如果错误代码未找到）

    Returns:
        中文错误消息
    """
    return ERROR_MESSAGES.get(error_code, default or "发生未知错误")


# ============ 辅助函数 ============

def get_cookies_dir() -> Path:
    """获取Cookie文件夹路径"""
    from src.core.downloaders.cookie_manager import get_cookie_base_dir
    return get_cookie_base_dir()


# 平台ID到Cookie文件名的映射
PLATFORM_COOKIE_FILES = {
    "bilibili": "bilibili_cookies.txt",
    "douyin": "douyin_cookies.txt",
    "kuaishou": "kuaishou_cookies.txt",
    "xiaohongshu": "xiaohongshu_cookies.txt",
    "weibo": "weibo_cookies.txt",
    "tencent": "tencent_cookies.txt",
    "iqiyi": "iqiyi_cookies.txt",
    "youku": "youku_cookies.txt",
    "mango": "mango_cookies.txt",
}


def save_cookies_to_file(platform_id: str, cookies: str) -> bool:
    """保存Cookie到文件

    Args:
        platform_id: 平台ID
        cookies: Netscape格式的Cookie内容

    Returns:
        是否保存成功
    """
    try:
        filename = PLATFORM_COOKIE_FILES.get(platform_id)
        if not filename:
            logger.error(f"未知平台: {platform_id}")
            return False

        cookies_dir = get_cookies_dir()
        cookies_dir.mkdir(parents=True, exist_ok=True)
        cookie_file = cookies_dir / filename

        # 验证Cookie格式
        is_valid, errors, _ = validate_netscape_cookie_format(cookies)
        if not is_valid:
            logger.warning(f"Cookie格式验证有警告: {errors[:3]}")

        # 保存Cookie
        write_cookie_file(cookie_file, cookies)
        logger.info(f"已保存 {platform_id} Cookie 到 {cookie_file}")
        return True

    except Exception as e:
        logger.error(f"保存 {platform_id} Cookie 失败: {e}")
        return False


def get_error_response(error_code: str, message: Optional[str] = None) -> dict:
    """生成统一的错误响应

    Args:
        error_code: 错误代码
        message: 自定义中文错误消息（可选，如果不提供则使用默认消息）

    Returns:
        错误响应字典
    """
    return {
        "status": "error",
        "error": message or get_error_message(error_code),
        "error_code": error_code
    }


def classify_exception(e: Exception) -> tuple[str, str]:
    """根据异常类型分类错误

    Args:
        e: 异常对象

    Returns:
        (error_code, error_message) 元组
    """
    error_str = str(e).lower()

    # 网络超时
    if isinstance(e, TimeoutError) or "timeout" in error_str:
        return QRLoginErrorCode.NETWORK_TIMEOUT, get_error_message(QRLoginErrorCode.NETWORK_TIMEOUT)

    # 浏览器/Playwright错误
    if "browser" in error_str or "playwright" in error_str or "chromium" in error_str:
        return QRLoginErrorCode.BROWSER_ERROR, get_error_message(QRLoginErrorCode.BROWSER_ERROR)

    # 验证码/滑块验证
    if "验证" in str(e) or "captcha" in error_str or "verify" in error_str:
        return QRLoginErrorCode.VERIFICATION_REQUIRED, get_error_message(QRLoginErrorCode.VERIFICATION_REQUIRED)

    # Cookie转换失败
    if "cookie" in error_str and ("convert" in error_str or "转换" in str(e)):
        return QRLoginErrorCode.COOKIE_CONVERSION_FAILED, get_error_message(QRLoginErrorCode.COOKIE_CONVERSION_FAILED)

    # 网络连接错误
    if "connection" in error_str or "network" in error_str or "网络" in str(e):
        return QRLoginErrorCode.NETWORK_TIMEOUT, "网络连接失败，请检查网络后重试"

    # 默认为API错误
    return QRLoginErrorCode.API_ERROR, f"请求失败: {str(e)}"


# ============ API 端点 ============

@router.get("/supported", response_model=QRSupportedPlatformsResponse)
async def get_supported_platforms():
    """获取支持扫码登录的平台列表

    Returns:
        支持扫码登录的平台列表，包含平台ID、中文名称、二维码过期时间和启用状态
    """
    try:
        registry = get_qr_registry()
        platforms_data = registry.get_supported_platforms()

        platforms = [
            QRSupportedPlatform(
                platform_id=p["platform_id"],
                platform_name_zh=p["platform_name_zh"],
                qr_expiry_seconds=p["qr_expiry_seconds"],
                enabled=p["enabled"]
            )
            for p in platforms_data
        ]

        return QRSupportedPlatformsResponse(platforms=platforms)

    except Exception as e:
        logger.error(f"获取支持平台列表失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=get_error_response(
                QRLoginErrorCode.INTERNAL_ERROR,
                f"获取平台列表失败: {str(e)}"
            )
        )


@router.get("/{platform_id}/qrcode")
async def get_qrcode(platform_id: str):
    """获取平台登录二维码

    Args:
        platform_id: 平台ID（如 bilibili, douyin, kuaishou 等）

    Returns:
        二维码信息，包含二维码URL、key、过期时间和提示消息
    """
    try:
        service = get_qr_login_service()
        result = await service.get_qrcode(platform_id)

        return QRCodeResponse(
            qrcode_url=result.qrcode_url,
            qrcode_key=result.qrcode_key,
            expires_in=result.expires_in,
            message=result.message
        )

    except ValueError as e:
        # 平台不支持或未启用
        error_msg = str(e)
        if "不支持" in error_msg:
            error_code = QRLoginErrorCode.PLATFORM_NOT_SUPPORTED
        else:
            error_code = QRLoginErrorCode.PLATFORM_DISABLED

        raise HTTPException(
            status_code=400,
            detail=get_error_response(error_code, error_msg)
        )

    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=get_error_response(QRLoginErrorCode.NETWORK_TIMEOUT)
        )

    except Exception as e:
        logger.error(f"获取 {platform_id} 二维码失败: {e}")
        error_code, error_msg = classify_exception(e)

        status_code = 504 if error_code == QRLoginErrorCode.NETWORK_TIMEOUT else 500
        raise HTTPException(
            status_code=status_code,
            detail=get_error_response(error_code, error_msg)
        )


@router.post("/{platform_id}/qrcode/check")
async def check_qrcode_status(platform_id: str):
    """检查扫码状态

    Args:
        platform_id: 平台ID

    Returns:
        扫码状态，包含状态码和消息
    """
    try:
        service = get_qr_login_service()
        result = await service.check_status(platform_id)

        # 如果登录成功，保存Cookie
        if result.status == QRLoginStatus.SUCCESS and result.cookies:
            save_success = save_cookies_to_file(platform_id, result.cookies)
            if not save_success:
                # Cookie保存失败，但登录本身成功了
                logger.warning(f"{platform_id} Cookie保存失败，但登录成功")

        return QRStatusResponse(
            status=result.status.value,
            message=result.message
        )

    except ValueError as e:
        # 平台不支持或未启用
        error_msg = str(e)
        if "不支持" in error_msg:
            error_code = QRLoginErrorCode.PLATFORM_NOT_SUPPORTED
        else:
            error_code = QRLoginErrorCode.PLATFORM_DISABLED

        raise HTTPException(
            status_code=400,
            detail=get_error_response(error_code, error_msg)
        )

    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=get_error_response(QRLoginErrorCode.NETWORK_TIMEOUT)
        )

    except Exception as e:
        logger.error(f"检查 {platform_id} 扫码状态失败: {e}")
        error_code, error_msg = classify_exception(e)

        status_code = 504 if error_code == QRLoginErrorCode.NETWORK_TIMEOUT else 500
        raise HTTPException(
            status_code=status_code,
            detail=get_error_response(error_code, error_msg)
        )


@router.post("/{platform_id}/qrcode/cancel")
async def cancel_qr_login(platform_id: str):
    """取消扫码登录并清理资源

    Args:
        platform_id: 平台ID

    Returns:
        操作结果
    """
    try:
        service = get_qr_login_service()
        await service.cancel_login(platform_id)

        return {
            "status": "success",
            "message": "已取消登录"
        }

    except Exception as e:
        logger.error(f"取消 {platform_id} 登录失败: {e}")
        # 取消操作即使失败也返回成功，避免前端卡住
        return {
            "status": "success",
            "message": "已取消登录"
        }


@router.post("/{platform_id}/enable")
async def enable_platform(platform_id: str, enabled: bool = Body(..., embed=True)):
    """启用或禁用平台扫码登录

    Args:
        platform_id: 平台ID
        enabled: 是否启用

    Returns:
        操作结果
    """
    try:
        registry = get_qr_registry()

        if not registry.has_platform(platform_id):
            raise HTTPException(
                status_code=404,
                detail=get_error_response(
                    QRLoginErrorCode.PLATFORM_NOT_SUPPORTED,
                    f"平台 {platform_id} 不存在"
                )
            )

        success = registry.set_enabled(platform_id, enabled)

        if success:
            status_text = "启用" if enabled else "禁用"
            return {
                "status": "success",
                "message": f"已{status_text}平台 {platform_id} 的扫码登录"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=get_error_response(
                    QRLoginErrorCode.INTERNAL_ERROR,
                    "设置失败"
                )
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置 {platform_id} 启用状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=get_error_response(
                QRLoginErrorCode.INTERNAL_ERROR,
                f"设置失败: {str(e)}"
            )
        )
