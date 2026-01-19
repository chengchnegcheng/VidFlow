"""
微信视频号 API

提供视频号嗅探、下载和证书管理的 API 端点。
"""
import logging
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.core.channels.models import (
    SnifferState,
    SnifferStatus,
    SnifferStartResult,
    DetectedVideo,
    ChannelsConfig,
    CertInfo,
    CertGenerateResult,
    ErrorCode,
    get_error_message,
    # 透明捕获相关
    CaptureMode,
    DriverState,
    CaptureState,
    DriverStatus,
    CaptureStatistics,
    CaptureStatus,
    CaptureConfig,
)
from src.core.channels.proxy_sniffer import ProxySniffer
from src.core.channels.certificate_manager import CertificateManager
from src.core.downloaders.channels_downloader import ChannelsDownloader
from src.core.channels.driver_manager import DriverManager
from src.core.channels.traffic_capture import WinDivertCapture
from src.core.channels.capture_config import CaptureConfigManager, get_config_manager


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])

# ============ 全局实例 ============

_sniffer: Optional[ProxySniffer] = None
_cert_manager: Optional[CertificateManager] = None
_downloader: Optional[ChannelsDownloader] = None
_config: ChannelsConfig = ChannelsConfig()
_driver_manager: Optional[DriverManager] = None
_traffic_capture: Optional[WinDivertCapture] = None
_capture_config_manager: Optional[CaptureConfigManager] = None


def _handle_video_detected(video: DetectedVideo) -> None:
    """当嗅探器检测到视频时更新捕获统计"""
    if _traffic_capture and _traffic_capture.is_running:
        try:
            _traffic_capture.update_video_detected()
        except Exception:
            logger.exception("Failed to update capture statistics")


def _handle_sni_detected(sni: str, dst_ip: str, dst_port: int) -> None:
    """当检测到视频号相关的 SNI 或 URL 时创建视频对象
    
    Args:
        sni: SNI 域名或完整的 HTTP URL
        dst_ip: 目标 IP
        dst_port: 目标端口
    """
    import hashlib
    from datetime import datetime
    from src.core.channels.models import DetectedVideo, EncryptionType
    
    try:
        # 检查是否是完整的 HTTP URL
        if sni.startswith('http://') or sni.startswith('https://'):
            # 已经是完整的 URL
            url = sni
            # 从 URL 中提取标题
            if 'wxapp.tc.qq.com' in sni or 'stodownload' in sni:
                title = f"视频号视频 (HTTP)"
            else:
                title = f"视频号视频 ({dst_ip})"
        elif sni.startswith('proxy:'):
            # 代理监控的结果 - 跳过，因为没有实际的视频 URL
            logger.debug(f"Skipping proxy detection result: {sni}")
            return
        elif sni.startswith('ip:'):
            # IP 检测的结果 - 创建占位符，标记为 ECH 加密
            # 提取 IP 地址
            ip_addr = sni.replace('ip:', '')
            url = f"https://{ip_addr}/"  # 使用 IP 作为临时 URL
            title = f"视频号视频 (ECH加密: {ip_addr})"
            logger.info(f"Created placeholder for ECH-encrypted video: {ip_addr}")
        else:
            # 普通 SNI 域名
            url = f"https://{sni}/"
            title = f"视频号视频 ({sni})"
        
        # 生成视频 ID
        video_id = hashlib.md5(f"{sni}:{dst_ip}:{dst_port}".encode()).hexdigest()[:16]
        
        # 创建视频对象
        video = DetectedVideo(
            id=video_id,
            url=url,
            title=title,
            detected_at=datetime.now(),
            encryption_type=EncryptionType.ECH if sni.startswith('ip:') else EncryptionType.UNKNOWN,
        )
        
        # 添加到嗅探器
        sniffer = get_sniffer_sync()
        if sniffer:
            added = sniffer.add_detected_video(video)
            if added:
                logger.info(f"Added video from SNI/URL: {sni[:80]}")
                # 更新统计
                if _traffic_capture:
                    _traffic_capture.update_video_detected()
    except Exception:
        logger.exception(f"Failed to handle SNI detection: {sni}")


def get_data_dir() -> Path:
    """获取数据目录"""
    from src.models.database import get_data_dir as _get_data_dir
    return _get_data_dir()


async def get_sniffer(transparent_mode: bool = False) -> ProxySniffer:
    """获取嗅探器实例

    Args:
        transparent_mode: 是否使用透明代理模式（用于 WinDivert 透明捕获）
                         False = 显式代理模式（用于手动配置代理）

    Returns:
        ProxySniffer 实例
    """
    global _sniffer
    if _sniffer is None:
        cert_dir = get_data_dir() / "channels" / "certs"
        _sniffer = ProxySniffer(port=_config.proxy_port, cert_dir=cert_dir, transparent_mode=transparent_mode)
    elif _sniffer.transparent_mode != transparent_mode:
        previous_port = _sniffer.port
        if _sniffer.is_running:
            logger.info(f"Stopping sniffer to switch mode: {_sniffer.transparent_mode} -> {transparent_mode}")
            # 等待停止完成，避免端口竞争
            await _sniffer.stop()
        cert_dir = get_data_dir() / "channels" / "certs"
        _sniffer = ProxySniffer(port=previous_port, cert_dir=cert_dir, transparent_mode=transparent_mode)
    _sniffer.set_on_video_detected(_handle_video_detected)
    return _sniffer


def get_sniffer_sync() -> ProxySniffer:
    """获取嗅探器实例（同步版本，仅用于获取当前实例，不切换模式）

    Returns:
        当前的 ProxySniffer 实例，如果不存在则返回 None
    """
    return _sniffer


def get_cert_manager() -> CertificateManager:
    """获取证书管理器实例"""
    global _cert_manager
    if _cert_manager is None:
        cert_dir = get_data_dir() / "channels" / "certs"
        _cert_manager = CertificateManager(cert_dir)
    return _cert_manager


def get_downloader() -> ChannelsDownloader:
    """获取下载器实例"""
    global _downloader
    if _downloader is None:
        output_dir = _config.download_dir or None
        _downloader = ChannelsDownloader(
            output_dir=output_dir,
            auto_decrypt=_config.auto_decrypt
        )
    return _downloader


def get_driver_manager() -> DriverManager:
    """获取驱动管理器实例"""
    global _driver_manager
    if _driver_manager is None:
        _driver_manager = DriverManager()
    return _driver_manager


def get_traffic_capture() -> WinDivertCapture:
    """获取透明捕获实例"""
    global _traffic_capture
    capture_config = get_capture_config_manager().config
    if _traffic_capture is None:
        _traffic_capture = WinDivertCapture(
            proxy_port=_config.proxy_port,
            target_processes=capture_config.target_processes,
        )
        # 设置 SNI 检测回调
        _traffic_capture.set_on_sni_detected(_handle_sni_detected)
    else:
        # 即使未运行也同步最新配置
        _traffic_capture.set_target_processes(capture_config.target_processes)
    return _traffic_capture


def get_capture_config_manager() -> CaptureConfigManager:
    """获取捕获配置管理器实例"""
    global _capture_config_manager
    if _capture_config_manager is None:
        config_path = get_data_dir() / "channels" / "capture_config.json"
        _capture_config_manager = CaptureConfigManager(str(config_path))
    return _capture_config_manager


# ============ 请求/响应模型 ============

class SnifferStartRequest(BaseModel):
    """启动嗅探器请求"""
    port: Optional[int] = None
    capture_mode: Optional[str] = "transparent"  # 透明捕获模式（Windows PC 端微信）


class SnifferStartResponse(BaseModel):
    """启动嗅探器响应"""
    success: bool
    proxy_address: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    capture_mode: str = "transparent"


class SnifferStatusResponse(BaseModel):
    """嗅探器状态响应"""
    state: str
    proxy_address: Optional[str] = None
    proxy_port: int
    videos_detected: int
    started_at: Optional[str] = None
    error_message: Optional[str] = None
    capture_mode: str = "transparent"
    capture_state: str = "stopped"
    capture_started_at: Optional[str] = None
    statistics: Optional[dict] = None


# ============ 驱动管理响应模型 ============

class DriverStatusResponse(BaseModel):
    """驱动状态响应"""
    state: str
    version: Optional[str] = None
    path: Optional[str] = None
    error_message: Optional[str] = None
    is_admin: bool = False


class DriverInstallResponse(BaseModel):
    """驱动安装响应"""
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None


# ============ 捕获配置响应模型 ============

class CaptureConfigResponse(BaseModel):
    """捕获配置响应"""
    capture_mode: str
    use_windivert: bool
    target_processes: List[str]
    no_detection_timeout: int
    log_unrecognized_domains: bool


class CaptureConfigUpdateRequest(BaseModel):
    """捕获配置更新请求"""
    capture_mode: Optional[str] = None
    use_windivert: Optional[bool] = None
    target_processes: Optional[List[str]] = None
    no_detection_timeout: Optional[int] = None
    log_unrecognized_domains: Optional[bool] = None


class DetectedVideoResponse(BaseModel):
    """检测到的视频响应"""
    id: str
    url: str
    title: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    filesize: Optional[int] = None
    thumbnail: Optional[str] = None
    detected_at: str
    encryption_type: str
    decryption_key: Optional[str] = None


class DownloadRequest(BaseModel):
    """下载请求"""
    url: str
    quality: str = "best"
    output_path: Optional[str] = None
    auto_decrypt: Optional[bool] = None


class DownloadResponse(BaseModel):
    """下载响应"""
    success: bool
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    task_id: Optional[str] = None


class CertInfoResponse(BaseModel):
    """证书信息响应"""
    exists: bool
    valid: bool
    expires_at: Optional[str] = None
    fingerprint: Optional[str] = None
    path: Optional[str] = None


class CertGenerateResponse(BaseModel):
    """证书生成响应"""
    success: bool
    cert_path: Optional[str] = None
    error_message: Optional[str] = None


class ConfigResponse(BaseModel):
    """配置响应"""
    proxy_port: int
    download_dir: str
    auto_decrypt: bool
    quality_preference: str
    clear_on_exit: bool


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    proxy_port: Optional[int] = None
    download_dir: Optional[str] = None
    auto_decrypt: Optional[bool] = None
    quality_preference: Optional[str] = None
    clear_on_exit: Optional[bool] = None


# ============ 嗅探器 API ============

@router.post("/sniffer/start", response_model=SnifferStartResponse)
async def start_sniffer(request: SnifferStartRequest = None):
    """启动代理嗅探器
    
    Args:
        request: 启动请求，可指定端口和捕获模式
        
    Returns:
        启动结果
    """
    try:
        capture_mode = CaptureMode.PROXY  # 默认使用代理模式
        if request and request.capture_mode:
            try:
                capture_mode = CaptureMode(request.capture_mode)
            except ValueError:
                capture_mode = CaptureMode.PROXY
        
        # 代理模式（推荐，使用 mitmproxy 解密 HTTPS）
        if capture_mode == CaptureMode.PROXY or capture_mode == CaptureMode.PROXY_ONLY:
            return await _start_proxy_capture(request)
        
        # 透明捕获模式（WinDivert 被动嗅探，无法解密 HTTPS）
        if capture_mode == CaptureMode.TRANSPARENT:
            return await _start_transparent_capture(request)
        
        # 默认使用代理模式
        return await _start_proxy_capture(request)
        
    except Exception as e:
        logger.exception("Failed to start sniffer")
        return SnifferStartResponse(
            success=False,
            error_message=f"启动失败: {str(e)}",
            capture_mode="proxy",
        )


async def _start_proxy_capture(request: SnifferStartRequest) -> SnifferStartResponse:
    """启动代理捕获模式
    
    使用 mitmproxy 作为 HTTPS 代理，可以解密流量并提取视频 URL。
    需要安装 CA 证书到系统。
    
    Args:
        request: 启动请求
        
    Returns:
        启动结果
    """
    global _sniffer
    
    try:
        cert_dir = get_data_dir() / "channels" / "certs"
        port = request.port if request and request.port else _config.proxy_port
        
        # 检查证书是否存在
        cert_manager = get_cert_manager()
        if not cert_manager.is_cert_valid():
            # 自动生成证书
            result = cert_manager.generate_ca_cert()
            if not result.success:
                return SnifferStartResponse(
                    success=False,
                    error_message=f"证书生成失败: {result.error_message}",
                    capture_mode="proxy",
                )
            logger.info(f"Generated CA certificate: {result.cert_path}")
        
        # 创建或获取 sniffer 实例
        if _sniffer is None or _sniffer.port != port:
            if _sniffer and _sniffer.is_running:
                await _sniffer.stop()
            _sniffer = ProxySniffer(port=port, cert_dir=cert_dir, transparent_mode=False)
            _sniffer.set_on_video_detected(_handle_video_detected)
        
        # 启动代理
        result = await _sniffer.start()
        
        if not result.success:
            return SnifferStartResponse(
                success=False,
                error_message=result.error_message,
                error_code=result.error_code,
                capture_mode="proxy",
            )
        
        # 获取证书信息
        cert_info = cert_manager.get_cert_info()
        
        return SnifferStartResponse(
            success=True,
            proxy_address=f"127.0.0.1:{port}",
            capture_mode="proxy",
            error_message=f"代理已启动。请设置系统代理为 127.0.0.1:{port}，并安装 CA 证书: {cert_info.path}" if cert_info.path else None,
        )
        
    except Exception as e:
        logger.exception("Failed to start proxy capture")
        return SnifferStartResponse(
            success=False,
            error_message=f"启动失败: {str(e)}",
            capture_mode="proxy",
        )


async def _start_transparent_capture(request: SnifferStartRequest) -> SnifferStartResponse:
    """启动透明捕获模式
    
    使用 mitmproxy 内置的 local 模式，自动使用 WinDivert 拦截微信流量。
    mitmproxy 10.2+ 内置了 WinDivert 支持，不需要我们自己实现。
    
    Args:
        request: 启动请求
        
    Returns:
        启动结果
    """
    global _traffic_capture, _sniffer
    
    try:
        # 使用 mitmproxy 的 local 模式，它会自动处理 WinDivert
        cert_dir = get_data_dir() / "channels" / "certs"
        port = request.port if request and request.port else _config.proxy_port
        
        # 检查证书
        cert_manager = get_cert_manager()
        if not cert_manager.is_cert_valid():
            result = cert_manager.generate_ca_cert()
            if not result.success:
                return SnifferStartResponse(
                    success=False,
                    error_message=f"证书生成失败: {result.error_message}",
                    capture_mode="transparent",
                )
            logger.info(f"Generated CA certificate: {result.cert_path}")
        
        # 创建 sniffer 实例（transparent_mode=True 启用 local 模式）
        if _sniffer is None or _sniffer.port != port:
            if _sniffer and _sniffer.is_running:
                await _sniffer.stop()
            _sniffer = ProxySniffer(port=port, cert_dir=cert_dir, transparent_mode=True)
            _sniffer.set_on_video_detected(_handle_video_detected)
        
        # 启动 mitmproxy（它会自动启动 WinDivert）
        sniffer_result = await _sniffer.start()
        if not sniffer_result.success:
            return SnifferStartResponse(
                success=False,
                error_message=f"mitmproxy 启动失败: {sniffer_result.error_message}",
                error_code=sniffer_result.error_code,
                capture_mode="transparent",
            )
        
        logger.info(f"mitmproxy local mode started (auto WinDivert)")
        
        return SnifferStartResponse(
            success=True,
            proxy_address=f"Local 模式 (自动拦截微信)",
            capture_mode="transparent",
        )
        
    except Exception as e:
        logger.exception("Failed to start transparent capture")
        
        return SnifferStartResponse(
            success=False,
            error_message=f"启动失败: {str(e)}",
            capture_mode="transparent",
        )


@router.post("/sniffer/stop")
async def stop_sniffer():
    """停止代理嗅探器
    
    Returns:
        操作结果
    """
    try:
        # 停止透明捕获
        capture = get_traffic_capture()
        if capture.is_running:
            await capture.stop()
        
        # 停止代理（使用 get_sniffer_sync 避免意外的模式切换）
        sniffer = get_sniffer_sync()
        if sniffer:
            success = await sniffer.stop()
        else:
            success = True  # 如果没有运行的 sniffer，认为停止成功
        
        return {
            "success": success,
            "message": "嗅探器已停止" if success else "停止失败"
        }
        
    except Exception as e:
        logger.exception("Failed to stop sniffer")
        return {
            "success": False,
            "message": f"停止失败: {str(e)}"
        }


@router.get("/sniffer/status", response_model=SnifferStatusResponse)
async def get_sniffer_status():
    """获取嗅探器状态
    
    Returns:
        嗅探器当前状态
    """
    try:
        # 检查透明捕获状态
        capture = get_traffic_capture()
        capture_status = capture.get_status()
        
        sniffer = get_sniffer_sync()
        
        # 被动嗅探模式：只使用 WinDivert，不需要 mitmproxy
        if capture.is_running:
            # 透明捕获正在运行
            videos_detected = len(capture.get_detected_snis()) if hasattr(capture, 'get_detected_snis') else 0
            
            # 如果有 sniffer，也获取它检测到的视频数量
            if sniffer:
                videos_detected = max(videos_detected, sniffer.get_status().videos_detected)
            
            statistics = capture_status.statistics.to_dict() if capture_status.statistics else None
            
            return SnifferStatusResponse(
                state="running",
                proxy_address="被动嗅探模式 (无需代理)",
                proxy_port=_config.proxy_port,
                videos_detected=videos_detected,
                started_at=capture_status.started_at.isoformat() if capture_status.started_at else None,
                error_message=None,
                capture_mode="transparent",
                capture_state=capture_status.state.value,
                capture_started_at=capture_status.started_at.isoformat() if capture_status.started_at else None,
                statistics=statistics,
            )
        
        if not sniffer:
            # 如果没有 sniffer 实例，返回默认状态
            return SnifferStatusResponse(
                state=SnifferState.STOPPED.value,
                proxy_port=_config.proxy_port,
                videos_detected=0,
                capture_mode="transparent",
                capture_state="stopped",
            )

        status = sniffer.get_status()
        capture_mode_str = "transparent"
        
        # 获取统计信息
        statistics = capture_status.statistics.to_dict() if capture_status.statistics else None
        
        return SnifferStatusResponse(
            state=status.state.value,
            proxy_address=status.proxy_address,
            proxy_port=status.proxy_port,
            videos_detected=status.videos_detected,
            started_at=status.started_at.isoformat() if status.started_at else None,
            error_message=status.error_message,
            capture_mode=capture_mode_str,
            capture_state=capture_status.state.value,
            capture_started_at=capture_status.started_at.isoformat() if capture_status.started_at else None,
            statistics=statistics,
        )
        
    except Exception as e:
        logger.exception("Failed to get sniffer status")
        return SnifferStatusResponse(
            state=SnifferState.ERROR.value,
            proxy_port=_config.proxy_port,
            videos_detected=0,
            error_message=str(e),
            capture_mode="transparent",
            capture_state="stopped",
            capture_started_at=None,
            statistics=None,
        )


# ============ 视频列表 API ============

@router.get("/videos", response_model=List[DetectedVideoResponse])
async def get_detected_videos():
    """获取检测到的视频列表
    
    Returns:
        检测到的视频列表
    """
    try:
        sniffer = get_sniffer_sync()
        if not sniffer:
            return []

        videos = sniffer.get_detected_videos()
        
        return [
            DetectedVideoResponse(
                id=v.id,
                url=v.url,
                title=v.title,
                duration=v.duration,
                resolution=v.resolution,
                filesize=v.filesize,
                thumbnail=v.thumbnail,
                detected_at=v.detected_at.isoformat(),
                encryption_type=v.encryption_type.value,
                decryption_key=v.decryption_key,
            )
            for v in videos
        ]
        
    except Exception as e:
        logger.exception("Failed to get detected videos")
        return []


@router.delete("/videos")
async def clear_detected_videos():
    """清空检测到的视频列表
    
    Returns:
        操作结果
    """
    try:
        sniffer = get_sniffer_sync()
        if not sniffer:
            return {
                "success": True,
                "message": "没有运行的嗅探器"
            }

        sniffer.clear_videos()
        
        return {
            "success": True,
            "message": "视频列表已清空"
        }
        
    except Exception as e:
        logger.exception("Failed to clear videos")
        return {
            "success": False,
            "message": f"清空失败: {str(e)}"
        }


class AddVideoRequest(BaseModel):
    """手动添加视频请求"""
    url: str
    title: Optional[str] = None


class AddVideoResponse(BaseModel):
    """手动添加视频响应"""
    success: bool
    video: Optional[DetectedVideoResponse] = None
    error_message: Optional[str] = None


@router.post("/videos/add", response_model=AddVideoResponse)
async def add_video_manually(request: AddVideoRequest):
    """手动添加视频 URL
    
    用于从其他工具（如浏览器开发者工具、Fiddler 等）获取视频 URL 后手动添加。
    
    Args:
        request: 添加请求，包含 URL 和可选标题
        
    Returns:
        添加结果
    """
    try:
        # 确保有 sniffer 实例
        cert_dir = get_data_dir() / "channels" / "certs"
        global _sniffer
        if _sniffer is None:
            _sniffer = ProxySniffer(port=_config.proxy_port, cert_dir=cert_dir, transparent_mode=False)
            _sniffer.set_on_video_detected(_handle_video_detected)
        
        # 添加视频
        video = _sniffer.add_video_from_url(request.url, request.title)
        
        if video:
            return AddVideoResponse(
                success=True,
                video=DetectedVideoResponse(
                    id=video.id,
                    url=video.url,
                    title=video.title,
                    duration=video.duration,
                    resolution=video.resolution,
                    filesize=video.filesize,
                    thumbnail=video.thumbnail,
                    detected_at=video.detected_at.isoformat(),
                    encryption_type=video.encryption_type.value,
                    decryption_key=video.decryption_key,
                ),
            )
        else:
            return AddVideoResponse(
                success=False,
                error_message="视频已存在或 URL 无效",
            )
        
    except Exception as e:
        logger.exception("Failed to add video manually")
        return AddVideoResponse(
            success=False,
            error_message=f"添加失败: {str(e)}",
        )


# ============ 下载 API ============

@router.post("/download", response_model=DownloadResponse)
async def download_video(request: DownloadRequest):
    """下载视频
    
    Args:
        request: 下载请求
        
    Returns:
        下载结果
    """
    try:
        downloader = get_downloader()
        
        result = await downloader.download_video(
            url=request.url,
            quality=request.quality,
            output_path=request.output_path,
            auto_decrypt=request.auto_decrypt,
        )
        
        return DownloadResponse(
            success=result.get("success", False),
            file_path=result.get("file_path"),
            file_size=result.get("file_size"),
            error=result.get("error"),
            error_code=result.get("error_code"),
            task_id=result.get("task_id"),
        )
        
    except Exception as e:
        logger.exception("Failed to download video")
        return DownloadResponse(
            success=False,
            error=f"下载失败: {str(e)}",
        )


@router.post("/download/cancel")
async def cancel_download(task_id: str = Body(..., embed=True)):
    """取消下载
    
    Args:
        task_id: 任务 ID
        
    Returns:
        操作结果
    """
    try:
        downloader = get_downloader()
        success = downloader.cancel_download(task_id)
        
        return {
            "success": success,
            "message": "下载已取消" if success else "取消失败"
        }
        
    except Exception as e:
        logger.exception("Failed to cancel download")
        return {
            "success": False,
            "message": f"取消失败: {str(e)}"
        }


# ============ 证书 API ============

@router.get("/certificate", response_model=CertInfoResponse)
async def get_certificate_info():
    """获取证书信息
    
    Returns:
        证书信息
    """
    try:
        cert_manager = get_cert_manager()
        info = cert_manager.get_cert_info()
        
        return CertInfoResponse(
            exists=info.exists,
            valid=info.valid,
            expires_at=info.expires_at.isoformat() if info.expires_at else None,
            fingerprint=info.fingerprint,
            path=info.path,
        )
        
    except Exception as e:
        logger.exception("Failed to get certificate info")
        return CertInfoResponse(
            exists=False,
            valid=False,
        )


@router.post("/certificate/generate", response_model=CertGenerateResponse)
async def generate_certificate():
    """生成 CA 证书
    
    Returns:
        生成结果
    """
    try:
        cert_manager = get_cert_manager()
        result = cert_manager.generate_ca_cert()
        
        return CertGenerateResponse(
            success=result.success,
            cert_path=result.cert_path,
            error_message=result.error_message,
        )
        
    except Exception as e:
        logger.exception("Failed to generate certificate")
        return CertGenerateResponse(
            success=False,
            error_message=f"生成失败: {str(e)}",
        )


@router.post("/certificate/export")
async def export_certificate(export_path: str = Body(..., embed=True)):
    """导出 CA 证书
    
    Args:
        export_path: 导出路径
        
    Returns:
        操作结果
    """
    try:
        cert_manager = get_cert_manager()
        success = cert_manager.export_cert(Path(export_path))
        
        return {
            "success": success,
            "message": "证书已导出" if success else "导出失败",
            "path": export_path if success else None,
        }
        
    except Exception as e:
        logger.exception("Failed to export certificate")
        return {
            "success": False,
            "message": f"导出失败: {str(e)}",
        }


@router.get("/certificate/download")
async def download_certificate():
    """下载 CA 证书文件
    
    Returns:
        证书文件
    """
    try:
        cert_manager = get_cert_manager()
        
        if not cert_manager.is_cert_valid():
            raise HTTPException(
                status_code=404,
                detail={"error": get_error_message(ErrorCode.CERT_MISSING)}
            )
        
        cert_path = cert_manager.ca_cert_path
        
        return FileResponse(
            path=str(cert_path),
            filename="VidFlow-CA.pem",
            media_type="application/x-pem-file",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to download certificate")
        raise HTTPException(
            status_code=500,
            detail={"error": f"下载失败: {str(e)}"}
        )


@router.get("/certificate/instructions")
async def get_certificate_instructions():
    """获取证书安装说明
    
    Returns:
        安装说明
    """
    try:
        cert_manager = get_cert_manager()
        instructions = cert_manager.get_install_instructions()
        
        return {
            "instructions": instructions
        }
        
    except Exception as e:
        logger.exception("Failed to get instructions")
        return {
            "instructions": "获取说明失败"
        }


# ============ 配置 API ============

@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """获取配置
    
    Returns:
        当前配置
    """
    return ConfigResponse(
        proxy_port=_config.proxy_port,
        download_dir=_config.download_dir,
        auto_decrypt=_config.auto_decrypt,
        quality_preference=_config.quality_preference,
        clear_on_exit=_config.clear_on_exit,
    )


@router.put("/config")
async def update_config(request: ConfigUpdateRequest):
    """更新配置
    
    Args:
        request: 配置更新请求
        
    Returns:
        操作结果
    """
    global _config, _sniffer, _downloader
    
    try:
        # 更新配置
        if request.proxy_port is not None:
            _config.proxy_port = request.proxy_port
        if request.download_dir is not None:
            _config.download_dir = request.download_dir
        if request.auto_decrypt is not None:
            _config.auto_decrypt = request.auto_decrypt
        if request.quality_preference is not None:
            _config.quality_preference = request.quality_preference
        if request.clear_on_exit is not None:
            _config.clear_on_exit = request.clear_on_exit
        
        # 重置实例以应用新配置
        _sniffer = None
        _downloader = None
        
        return {
            "success": True,
            "message": "配置已更新"
        }
        
    except Exception as e:
        logger.exception("Failed to update config")
        return {
            "success": False,
            "message": f"更新失败: {str(e)}"
        }


# ============ 驱动管理 API ============

@router.get("/driver/status", response_model=DriverStatusResponse)
async def get_driver_status():
    """获取 WinDivert 驱动状态
    
    Returns:
        驱动状态
    """
    try:
        driver_manager = get_driver_manager()
        status = driver_manager.get_status()
        
        return DriverStatusResponse(
            state=status.state.value,
            version=status.version,
            path=status.path,
            error_message=status.error_message,
            is_admin=status.is_admin,
        )
        
    except Exception as e:
        logger.exception("Failed to get driver status")
        return DriverStatusResponse(
            state=DriverState.ERROR.value,
            error_message=str(e),
            is_admin=False,
        )


@router.post("/driver/install", response_model=DriverInstallResponse)
async def install_driver():
    """安装 WinDivert 驱动
    
    Returns:
        安装结果
    """
    try:
        driver_manager = get_driver_manager()
        result = driver_manager.install()
        
        return DriverInstallResponse(
            success=result.success,
            error_code=result.error_code,
            error_message=result.error_message,
        )
        
    except Exception as e:
        logger.exception("Failed to install driver")
        return DriverInstallResponse(
            success=False,
            error_message=f"安装失败: {str(e)}",
        )


@router.post("/driver/request-admin")
async def request_admin_restart():
    """请求以管理员身份重启
    
    Returns:
        操作结果
    """
    try:
        driver_manager = get_driver_manager()
        success = driver_manager.request_admin_restart()
        
        return {
            "success": success,
            "message": "已请求管理员权限" if success else "请求失败"
        }
        
    except Exception as e:
        logger.exception("Failed to request admin restart")
        return {
            "success": False,
            "message": f"请求失败: {str(e)}"
        }


# ============ 捕获配置 API ============

@router.get("/capture/config", response_model=CaptureConfigResponse)
async def get_capture_config():
    """获取捕获配置
    
    Returns:
        当前捕获配置
    """
    try:
        config_manager = get_capture_config_manager()
        config = config_manager.config
        
        return CaptureConfigResponse(
            capture_mode=config.capture_mode.value,
            use_windivert=config.use_windivert,
            target_processes=config.target_processes,
            no_detection_timeout=config.no_detection_timeout,
            log_unrecognized_domains=config.log_unrecognized_domains,
        )
        
    except Exception as e:
        logger.exception("Failed to get capture config")
        # 返回默认配置
        return CaptureConfigResponse(
            capture_mode="transparent",
            use_windivert=True,
            target_processes=["WeChat.exe", "WeChatAppEx.exe"],
            no_detection_timeout=60,
            log_unrecognized_domains=True,
        )


@router.put("/capture/config", response_model=CaptureConfigResponse)
async def update_capture_config(request: CaptureConfigUpdateRequest):
    """更新捕获配置
    
    Args:
        request: 配置更新请求
        
    Returns:
        更新后的配置
    """
    try:
        config_manager = get_capture_config_manager()
        
        # 构建更新参数
        update_kwargs = {}
        if request.capture_mode is not None:
            update_kwargs['capture_mode'] = request.capture_mode
        if request.use_windivert is not None:
            update_kwargs['use_windivert'] = request.use_windivert
        if request.target_processes is not None:
            update_kwargs['target_processes'] = request.target_processes
        if request.no_detection_timeout is not None:
            update_kwargs['no_detection_timeout'] = request.no_detection_timeout
        if request.log_unrecognized_domains is not None:
            update_kwargs['log_unrecognized_domains'] = request.log_unrecognized_domains
        
        # 更新配置
        config = config_manager.update_config(**update_kwargs)
        
        # 同步到捕获服务（无论是否运行）
        capture = get_traffic_capture()
        capture.set_target_processes(config.target_processes)
        
        return CaptureConfigResponse(
            capture_mode=config.capture_mode.value,
            use_windivert=config.use_windivert,
            target_processes=config.target_processes,
            no_detection_timeout=config.no_detection_timeout,
            log_unrecognized_domains=config.log_unrecognized_domains,
        )
        
    except Exception as e:
        logger.exception("Failed to update capture config")
        raise HTTPException(
            status_code=500,
            detail={"error": f"更新失败: {str(e)}"}
        )


@router.get("/capture/statistics")
async def get_capture_statistics():
    """获取捕获统计信息
    
    Returns:
        统计信息
    """
    try:
        capture = get_traffic_capture()
        status = capture.get_status()
        
        return {
            "state": status.state.value,
            "mode": status.mode.value,
            "statistics": status.statistics.to_dict(),
            "started_at": status.started_at.isoformat() if status.started_at else None,
        }
        
    except Exception as e:
        logger.exception("Failed to get capture statistics")
        return {
            "state": "stopped",
            "mode": "transparent",
            "statistics": {
                "packets_intercepted": 0,
                "connections_redirected": 0,
                "videos_detected": 0,
                "last_detection_at": None,
                "unrecognized_domains": [],
            },
            "started_at": None,
        }


# ============ 深度优化 API（新增）============
# Validates: Requirements 1.1, 2.4, 2.5, 4.3, 7.4, 10.1

from src.core.channels.proxy_detector import ProxyDetector
from src.core.channels.config_manager import ConfigManager
from src.core.channels.quic_manager import QUICManager
from src.core.channels.multi_mode_sniffer import MultiModeSniffer

# 全局实例
_proxy_detector: Optional[ProxyDetector] = None
_multi_mode_config_manager: Optional[ConfigManager] = None
_quic_manager: Optional[QUICManager] = None
_multi_mode_sniffer: Optional[MultiModeSniffer] = None


def get_proxy_detector() -> ProxyDetector:
    """获取代理检测器实例"""
    global _proxy_detector
    if _proxy_detector is None:
        _proxy_detector = ProxyDetector()
    return _proxy_detector


def get_multi_mode_config_manager() -> ConfigManager:
    """获取多模式配置管理器实例"""
    global _multi_mode_config_manager
    if _multi_mode_config_manager is None:
        config_path = get_data_dir() / "channels" / "multi_mode_config.json"
        _multi_mode_config_manager = ConfigManager(config_path)
        _multi_mode_config_manager.load()
    return _multi_mode_config_manager


def get_quic_manager() -> QUICManager:
    """获取QUIC管理器实例"""
    global _quic_manager
    if _quic_manager is None:
        _quic_manager = QUICManager()
    return _quic_manager


def get_multi_mode_sniffer() -> MultiModeSniffer:
    """获取多模式嗅探器实例"""
    global _multi_mode_sniffer
    if _multi_mode_sniffer is None:
        config_manager = get_multi_mode_config_manager()
        _multi_mode_sniffer = MultiModeSniffer(config=config_manager.get_config())
    return _multi_mode_sniffer


# ============ 代理检测 API ============

class ProxyInfoResponse(BaseModel):
    """代理信息响应"""
    proxy_type: str
    proxy_mode: str
    process_name: Optional[str] = None
    process_pid: Optional[int] = None
    api_address: Optional[str] = None
    is_tun_enabled: bool = False
    is_fake_ip_enabled: bool = False


@router.get("/proxy/detect", response_model=ProxyInfoResponse)
async def detect_proxy():
    """检测系统代理软件
    
    检测系统中运行的代理软件及其工作模式。
    
    Returns:
        代理信息
    """
    try:
        detector = get_proxy_detector()
        proxy_info = await detector.detect()
        
        return ProxyInfoResponse(
            proxy_type=proxy_info.proxy_type.value,
            proxy_mode=proxy_info.proxy_mode.value,
            process_name=proxy_info.process_name,
            process_pid=proxy_info.process_pid,
            api_address=proxy_info.api_address,
            is_tun_enabled=proxy_info.is_tun_enabled,
            is_fake_ip_enabled=proxy_info.is_fake_ip_enabled,
        )
        
    except Exception as e:
        logger.exception("Failed to detect proxy")
        return ProxyInfoResponse(
            proxy_type="none",
            proxy_mode="none",
        )


# ============ 捕获模式 API ============

class CaptureModeInfo(BaseModel):
    """捕获模式信息"""
    mode: str
    name: str
    description: str
    available: bool
    recommended: bool = False


class CaptureModesResponse(BaseModel):
    """可用捕获模式响应"""
    modes: List[CaptureModeInfo]
    current_mode: str
    recommended_mode: str


@router.get("/modes", response_model=CaptureModesResponse)
async def get_capture_modes():
    """获取可用的捕获模式
    
    Returns:
        可用模式列表和当前模式
    """
    try:
        sniffer = get_multi_mode_sniffer()
        available_modes = await sniffer.get_available_modes()
        current_mode = sniffer.get_current_mode()
        
        # 检测代理以确定推荐模式
        detector = get_proxy_detector()
        proxy_info = await detector.detect()
        
        # 根据代理情况推荐模式
        recommended = "hybrid"
        if proxy_info.proxy_type.value in ("clash", "clash_verge", "clash_meta"):
            recommended = "clash_api"
        elif proxy_info.proxy_type.value == "none":
            recommended = "windivert"
        
        modes = [
            CaptureModeInfo(
                mode="windivert",
                name="WinDivert透明捕获",
                description="无需配置代理，直接捕获流量。需要管理员权限。",
                available="windivert" in [m.value for m in available_modes],
                recommended=(recommended == "windivert"),
            ),
            CaptureModeInfo(
                mode="clash_api",
                name="Clash API监控",
                description="通过Clash API监控连接，与Clash完美兼容。",
                available="clash_api" in [m.value for m in available_modes],
                recommended=(recommended == "clash_api"),
            ),
            CaptureModeInfo(
                mode="system_proxy",
                name="系统代理拦截",
                description="使用mitmproxy作为系统代理，需要安装证书。",
                available="system_proxy" in [m.value for m in available_modes],
                recommended=(recommended == "system_proxy"),
            ),
            CaptureModeInfo(
                mode="hybrid",
                name="混合模式",
                description="自动选择最佳捕获策略，推荐使用。",
                available=True,
                recommended=(recommended == "hybrid"),
            ),
        ]
        
        return CaptureModesResponse(
            modes=modes,
            current_mode=current_mode.value,
            recommended_mode=recommended,
        )
        
    except Exception as e:
        logger.exception("Failed to get capture modes")
        return CaptureModesResponse(
            modes=[],
            current_mode="hybrid",
            recommended_mode="hybrid",
        )


class SwitchModeRequest(BaseModel):
    """切换模式请求"""
    mode: str


class SwitchModeResponse(BaseModel):
    """切换模式响应"""
    success: bool
    previous_mode: str
    current_mode: str
    error_message: Optional[str] = None


@router.post("/mode", response_model=SwitchModeResponse)
async def switch_capture_mode(request: SwitchModeRequest):
    """切换捕获模式
    
    切换到指定的捕获模式，保留已检测的视频。
    
    Args:
        request: 切换请求
        
    Returns:
        切换结果
    """
    try:
        sniffer = get_multi_mode_sniffer()
        previous_mode = sniffer.get_current_mode()
        
        # 转换模式字符串
        from src.core.channels.models import CaptureMode as CM
        try:
            new_mode = CM(request.mode)
        except ValueError:
            return SwitchModeResponse(
                success=False,
                previous_mode=previous_mode.value,
                current_mode=previous_mode.value,
                error_message=f"无效的模式: {request.mode}",
            )
        
        # 切换模式
        success = await sniffer.switch_mode(new_mode)
        current_mode = sniffer.get_current_mode()
        
        return SwitchModeResponse(
            success=success,
            previous_mode=previous_mode.value,
            current_mode=current_mode.value,
            error_message=None if success else "模式切换失败",
        )
        
    except Exception as e:
        logger.exception("Failed to switch capture mode")
        return SwitchModeResponse(
            success=False,
            previous_mode="unknown",
            current_mode="unknown",
            error_message=str(e),
        )


# ============ 诊断信息 API ============

class DiagnosticsResponse(BaseModel):
    """诊断信息响应"""
    detected_snis: List[str]
    detected_ips: List[str]
    wechat_processes: List[dict]
    proxy_info: Optional[dict] = None
    recent_errors: List[str]
    capture_log: List[str]
    statistics: dict


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def get_diagnostics():
    """获取诊断信息
    
    获取用于调试和诊断的详细信息。
    
    Returns:
        诊断信息
    """
    try:
        capture = get_traffic_capture()
        sniffer = get_multi_mode_sniffer()
        detector = get_proxy_detector()
        
        # 获取检测到的SNI
        detected_snis = capture.get_detected_snis() if hasattr(capture, 'get_detected_snis') else []
        
        # 获取微信进程信息
        wechat_manager = capture.get_wechat_process_manager()
        wechat_processes = [p.to_dict() for p in wechat_manager.get_processes()]
        
        # 获取代理信息
        proxy_info = await detector.detect()
        
        # 获取统计信息
        status = capture.get_status()
        statistics = status.statistics.to_dict() if status.statistics else {}
        
        # 获取检测到的IP（从ECH处理器）
        ech_handler = capture.get_ech_handler()
        detected_ips = ech_handler.get_ip_ranges()[:20]  # 限制数量
        
        return DiagnosticsResponse(
            detected_snis=detected_snis[:50],  # 限制数量
            detected_ips=detected_ips,
            wechat_processes=wechat_processes,
            proxy_info=proxy_info.to_dict(),
            recent_errors=[],  # TODO: 实现错误日志收集
            capture_log=[],  # TODO: 实现捕获日志
            statistics=statistics,
        )
        
    except Exception as e:
        logger.exception("Failed to get diagnostics")
        return DiagnosticsResponse(
            detected_snis=[],
            detected_ips=[],
            wechat_processes=[],
            proxy_info=None,
            recent_errors=[str(e)],
            capture_log=[],
            statistics={},
        )


# ============ QUIC管理 API ============

class QUICToggleRequest(BaseModel):
    """QUIC开关请求"""
    enabled: bool


class QUICStatusResponse(BaseModel):
    """QUIC状态响应"""
    blocking_enabled: bool
    packets_blocked: int
    packets_allowed: int
    target_processes: List[str]


@router.get("/quic/status", response_model=QUICStatusResponse)
async def get_quic_status():
    """获取QUIC阻止状态
    
    Returns:
        QUIC阻止状态
    """
    try:
        quic_manager = get_quic_manager()
        stats = quic_manager.get_stats()
        
        return QUICStatusResponse(
            blocking_enabled=quic_manager.is_blocking,
            packets_blocked=stats.packets_blocked,
            packets_allowed=stats.packets_allowed,
            target_processes=quic_manager.get_target_processes(),
        )
        
    except Exception as e:
        logger.exception("Failed to get QUIC status")
        return QUICStatusResponse(
            blocking_enabled=False,
            packets_blocked=0,
            packets_allowed=0,
            target_processes=[],
        )


@router.post("/quic/toggle", response_model=QUICStatusResponse)
async def toggle_quic_blocking(request: QUICToggleRequest):
    """切换QUIC阻止状态
    
    启用或禁用QUIC流量阻止。
    
    Args:
        request: 开关请求
        
    Returns:
        更新后的状态
    """
    try:
        quic_manager = get_quic_manager()
        
        if request.enabled:
            await quic_manager.start_blocking()
        else:
            await quic_manager.stop_blocking()
        
        stats = quic_manager.get_stats()
        
        return QUICStatusResponse(
            blocking_enabled=quic_manager.is_blocking,
            packets_blocked=stats.packets_blocked,
            packets_allowed=stats.packets_allowed,
            target_processes=quic_manager.get_target_processes(),
        )
        
    except Exception as e:
        logger.exception("Failed to toggle QUIC blocking")
        raise HTTPException(
            status_code=500,
            detail={"error": f"操作失败: {str(e)}"}
        )


# ============ 多模式配置 API ============

class MultiModeConfigResponse(BaseModel):
    """多模式配置响应"""
    preferred_mode: str
    auto_fallback: bool
    clash_api_address: str
    clash_api_secret: str
    quic_blocking_enabled: bool
    target_processes: List[str]
    diagnostic_mode: bool
    no_detection_timeout: int
    max_recovery_attempts: int


class MultiModeConfigUpdateRequest(BaseModel):
    """多模式配置更新请求"""
    preferred_mode: Optional[str] = None
    auto_fallback: Optional[bool] = None
    clash_api_address: Optional[str] = None
    clash_api_secret: Optional[str] = None
    quic_blocking_enabled: Optional[bool] = None
    target_processes: Optional[List[str]] = None
    diagnostic_mode: Optional[bool] = None
    no_detection_timeout: Optional[int] = None
    max_recovery_attempts: Optional[int] = None


@router.get("/config/multi-mode", response_model=MultiModeConfigResponse)
async def get_multi_mode_config():
    """获取多模式捕获配置
    
    Returns:
        当前配置
    """
    try:
        config_manager = get_multi_mode_config_manager()
        config = config_manager.get_config()
        
        return MultiModeConfigResponse(
            preferred_mode=config.preferred_mode.value,
            auto_fallback=config.auto_fallback,
            clash_api_address=config.clash_api_address,
            clash_api_secret=config.clash_api_secret,
            quic_blocking_enabled=config.quic_blocking_enabled,
            target_processes=config.target_processes,
            diagnostic_mode=config.diagnostic_mode,
            no_detection_timeout=config.no_detection_timeout,
            max_recovery_attempts=config.max_recovery_attempts,
        )
        
    except Exception as e:
        logger.exception("Failed to get multi-mode config")
        raise HTTPException(
            status_code=500,
            detail={"error": f"获取配置失败: {str(e)}"}
        )


@router.put("/config/multi-mode", response_model=MultiModeConfigResponse)
async def update_multi_mode_config(request: MultiModeConfigUpdateRequest):
    """更新多模式捕获配置
    
    Args:
        request: 配置更新请求
        
    Returns:
        更新后的配置
    """
    try:
        config_manager = get_multi_mode_config_manager()
        
        # 构建更新参数
        update_kwargs = {}
        if request.preferred_mode is not None:
            update_kwargs['preferred_mode'] = request.preferred_mode
        if request.auto_fallback is not None:
            update_kwargs['auto_fallback'] = request.auto_fallback
        if request.clash_api_address is not None:
            update_kwargs['clash_api_address'] = request.clash_api_address
        if request.clash_api_secret is not None:
            update_kwargs['clash_api_secret'] = request.clash_api_secret
        if request.quic_blocking_enabled is not None:
            update_kwargs['quic_blocking_enabled'] = request.quic_blocking_enabled
        if request.target_processes is not None:
            update_kwargs['target_processes'] = request.target_processes
        if request.diagnostic_mode is not None:
            update_kwargs['diagnostic_mode'] = request.diagnostic_mode
        if request.no_detection_timeout is not None:
            update_kwargs['no_detection_timeout'] = request.no_detection_timeout
        if request.max_recovery_attempts is not None:
            update_kwargs['max_recovery_attempts'] = request.max_recovery_attempts
        
        # 更新配置
        config = config_manager.update_config(**update_kwargs)
        
        # 验证配置
        errors = config.validate()
        if errors:
            raise HTTPException(
                status_code=400,
                detail={"error": f"配置验证失败: {', '.join(errors)}"}
            )
        
        # 保存配置
        config_manager.save()
        
        return MultiModeConfigResponse(
            preferred_mode=config.preferred_mode.value,
            auto_fallback=config.auto_fallback,
            clash_api_address=config.clash_api_address,
            clash_api_secret=config.clash_api_secret,
            quic_blocking_enabled=config.quic_blocking_enabled,
            target_processes=config.target_processes,
            diagnostic_mode=config.diagnostic_mode,
            no_detection_timeout=config.no_detection_timeout,
            max_recovery_attempts=config.max_recovery_attempts,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update multi-mode config")
        raise HTTPException(
            status_code=500,
            detail={"error": f"更新配置失败: {str(e)}"}
        )


@router.post("/config/multi-mode/reset")
async def reset_multi_mode_config():
    """重置多模式配置为默认值
    
    Returns:
        操作结果
    """
    try:
        config_manager = get_multi_mode_config_manager()
        config_manager.reset_to_defaults()
        config_manager.save()
        
        return {
            "success": True,
            "message": "配置已重置为默认值"
        }
        
    except Exception as e:
        logger.exception("Failed to reset multi-mode config")
        return {
            "success": False,
            "message": f"重置失败: {str(e)}"
        }


@router.post("/config/multi-mode/export")
async def export_multi_mode_config(export_path: str = Body(..., embed=True)):
    """导出多模式配置
    
    Args:
        export_path: 导出路径
        
    Returns:
        操作结果
    """
    try:
        config_manager = get_multi_mode_config_manager()
        success = config_manager.export_config(Path(export_path))
        
        return {
            "success": success,
            "message": "配置已导出" if success else "导出失败",
            "path": export_path if success else None,
        }
        
    except Exception as e:
        logger.exception("Failed to export multi-mode config")
        return {
            "success": False,
            "message": f"导出失败: {str(e)}"
        }


@router.post("/config/multi-mode/import")
async def import_multi_mode_config(import_path: str = Body(..., embed=True)):
    """导入多模式配置
    
    Args:
        import_path: 导入路径
        
    Returns:
        操作结果
    """
    try:
        config_manager = get_multi_mode_config_manager()
        config = config_manager.import_config(Path(import_path))
        
        if config:
            config_manager.save()
            return {
                "success": True,
                "message": "配置已导入"
            }
        else:
            return {
                "success": False,
                "message": "导入失败：无效的配置文件"
            }
        
    except Exception as e:
        logger.exception("Failed to import multi-mode config")
        return {
            "success": False,
            "message": f"导入失败: {str(e)}"
        }
