"""
频道视频捕获和下载 API
"""
import logging
from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path

from ..core.channels.proxy_sniffer import ProxySniffer
from ..core.downloaders.channels_downloader import ChannelsDownloader
from ..models.database import get_data_dir

router = APIRouter(prefix="/api/channels", tags=["channels"])
logger = logging.getLogger(__name__)

# 全局实例
_sniffer: Optional[ProxySniffer] = None
_downloader: Optional[ChannelsDownloader] = None


def get_sniffer() -> ProxySniffer:
    """获取嗅探器实例"""
    global _sniffer
    if _sniffer is None:
        _sniffer = ProxySniffer(port=8888, transparent_mode=True)
    return _sniffer


def get_downloader() -> ChannelsDownloader:
    """获取下载器实例"""
    global _downloader
    if _downloader is None:
        download_dir = get_data_dir() / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        _downloader = ChannelsDownloader(output_dir=str(download_dir), auto_decrypt=True)
    return _downloader


# ==================== 数据模型 ====================

class SnifferStatus(BaseModel):
    """嗅探器状态"""
    state: str = "stopped"
    proxy_port: int = 8888
    videos_detected: int = 0
    capture_mode: str = "transparent"
    capture_state: str = "stopped"


class VideoInfo(BaseModel):
    """视频信息"""
    url: str
    title: Optional[str] = None
    platform: Optional[str] = None


class DownloadRequest(BaseModel):
    """下载请求"""
    url: str
    quality: Optional[str] = None
    output_path: Optional[str] = None
    auto_decrypt: bool = False
    decryption_key: Optional[str] = None


class ConfigUpdate(BaseModel):
    """配置更新"""
    proxy_port: Optional[int] = None
    download_dir: Optional[str] = None
    auto_decrypt: Optional[bool] = None
    quality_preference: Optional[str] = None
    clear_on_exit: Optional[bool] = None


# ==================== 嗅探器 API ====================

@router.get("/sniffer/status")
async def get_sniffer_status():
    """获取嗅探器状态"""
    try:
        sniffer = get_sniffer()
        status = sniffer.get_status()
        return status.to_dict()
    except Exception as e:
        logger.error(f"Error getting sniffer status: {e}")
        raise HTTPException(status_code=500, detail=f"获取嗅探器状态失败: {str(e)}")


@router.post("/sniffer/start")
async def start_sniffer(port: Optional[int] = None, capture_mode: Optional[str] = None):
    """启动嗅探器"""
    try:
        sniffer = get_sniffer()
        
        # 检查是否有管理员权限
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        
        if not is_admin:
            logger.warning("应用未以管理员权限运行，透明捕获可能无法工作")
            return {
                "success": False,
                "error_message": "需要管理员权限才能使用透明捕获模式。请以管理员身份重新启动应用。",
                "error_code": "ADMIN_REQUIRED",
                "requires_admin": True
            }
        
        result = await sniffer.start()
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error starting sniffer: {e}")
        raise HTTPException(status_code=500, detail=f"启动嗅探器失败: {str(e)}")


@router.post("/sniffer/stop")
async def stop_sniffer():
    """停止嗅探器"""
    try:
        sniffer = get_sniffer()
        success = await sniffer.stop()
        return {"success": success, "message": "嗅探器已停止" if success else "停止失败"}
    except Exception as e:
        logger.error(f"Error stopping sniffer: {e}")
        raise HTTPException(status_code=500, detail=f"停止嗅探器失败: {str(e)}")


# ==================== 视频管理 API ====================

@router.get("/videos")
async def get_videos():
    """获取检测到的视频列表"""
    try:
        sniffer = get_sniffer()
        videos = sniffer.get_detected_videos()
        logger.info(f"返回 {len(videos)} 个视频")
        return [video.to_dict() for video in videos]
    except Exception as e:
        logger.error(f"Error getting videos: {e}")
        raise HTTPException(status_code=500, detail=f"获取视频列表失败: {str(e)}")


@router.delete("/videos")
async def clear_videos():
    """清空视频列表"""
    try:
        sniffer = get_sniffer()
        sniffer.clear_videos()
        return {"success": True, "message": "视频列表已清空"}
    except Exception as e:
        logger.error(f"Error clearing videos: {e}")
        raise HTTPException(status_code=500, detail=f"清空视频列表失败: {str(e)}")


@router.post("/videos/add")
async def add_video(url: str = Body(...), title: Optional[str] = Body(None)):
    """手动添加视频 URL"""
    try:
        sniffer = get_sniffer()
        video = sniffer.add_video_from_url(url, title)
        if video:
            return {"success": True, "video": video.to_dict(), "message": "视频已添加"}
        else:
            return {"success": False, "error_message": "视频已存在或添加失败"}
    except Exception as e:
        logger.error(f"Error adding video: {e}")
        raise HTTPException(status_code=500, detail=f"添加视频失败: {str(e)}")


# ==================== 下载管理 API ====================

@router.post("/download")
async def download_video(request: DownloadRequest):
    """下载视频"""
    try:
        downloader = get_downloader()
        result = await downloader.download_video(
            url=request.url,
            quality=request.quality or "best",
            output_path=request.output_path,
            auto_decrypt=request.auto_decrypt,
            decryption_key=request.decryption_key,
        )
        return result
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        raise HTTPException(status_code=500, detail=f"下载视频失败: {str(e)}")


@router.post("/download/cancel")
async def cancel_download(task_id: str = Body(...)):
    """取消下载"""
    try:
        # TODO: 实现取消下载逻辑
        return {"success": True, "message": "下载已取消"}
    except Exception as e:
        logger.error(f"Error canceling download: {e}")
        raise HTTPException(status_code=500, detail=f"取消下载失败: {str(e)}")


@router.get("/download/tasks")
async def get_download_tasks():
    """获取下载任务列表"""
    try:
        # TODO: 实现获取下载任务列表逻辑
        return []
    except Exception as e:
        logger.error(f"Error getting download tasks: {e}")
        raise HTTPException(status_code=500, detail=f"获取下载任务失败: {str(e)}")


@router.delete("/download/tasks/{task_id}")
async def delete_download_task(task_id: str):
    """删除下载任务"""
    try:
        # TODO: 实现删除下载任务逻辑
        return {"success": True, "message": "任务已删除"}
    except Exception as e:
        logger.error(f"Error deleting download task: {e}")
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")


# ==================== 证书管理 API ====================

@router.get("/certificate")
async def get_cert_info():
    """获取证书信息"""
    try:
        # TODO: 实现获取证书信息逻辑
        return {"installed": False, "valid": False}
    except Exception as e:
        logger.error(f"Error getting cert info: {e}")
        raise HTTPException(status_code=500, detail=f"获取证书信息失败: {str(e)}")


@router.post("/certificate/generate")
async def generate_cert():
    """生成证书"""
    try:
        # TODO: 实现生成证书逻辑
        return {"success": True, "message": "证书已生成"}
    except Exception as e:
        logger.error(f"Error generating cert: {e}")
        raise HTTPException(status_code=500, detail=f"生成证书失败: {str(e)}")


@router.post("/certificate/export")
async def export_cert(export_path: str = Body(...)):
    """导出证书"""
    try:
        # TODO: 实现导出证书逻辑
        return {"success": True, "message": "证书已导出"}
    except Exception as e:
        logger.error(f"Error exporting cert: {e}")
        raise HTTPException(status_code=500, detail=f"导出证书失败: {str(e)}")


@router.get("/certificate/instructions")
async def get_cert_instructions():
    """获取证书安装说明"""
    try:
        # TODO: 实现获取证书安装说明逻辑
        return {"instructions": "证书安装说明"}
    except Exception as e:
        logger.error(f"Error getting cert instructions: {e}")
        raise HTTPException(status_code=500, detail=f"获取证书说明失败: {str(e)}")


# ==================== 配置管理 API ====================

@router.get("/config")
async def get_config():
    """获取配置"""
    try:
        # TODO: 实现获取配置逻辑
        return {
            "proxy_port": 8888,
            "download_dir": "",
            "auto_decrypt": False,
            "quality_preference": "best",
            "clear_on_exit": False
        }
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("/config")
async def update_config(config: ConfigUpdate):
    """更新配置"""
    try:
        # TODO: 实现更新配置逻辑
        return {"success": True, "message": "配置已更新"}
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


# ==================== 驱动管理 API ====================

@router.get("/driver/status")
async def get_driver_status():
    """获取驱动状态"""
    try:
        # TODO: 实现获取驱动状态逻辑
        return {"installed": False, "running": False}
    except Exception as e:
        logger.error(f"Error getting driver status: {e}")
        raise HTTPException(status_code=500, detail=f"获取驱动状态失败: {str(e)}")


@router.post("/driver/install")
async def install_driver():
    """安装驱动"""
    try:
        # TODO: 实现安装驱动逻辑
        return {"success": True, "message": "驱动已安装"}
    except Exception as e:
        logger.error(f"Error installing driver: {e}")
        raise HTTPException(status_code=500, detail=f"安装驱动失败: {str(e)}")


@router.post("/driver/request-admin")
async def request_admin_restart():
    """请求管理员权限重启"""
    try:
        # TODO: 实现请求管理员权限重启逻辑
        return {"success": True, "message": "已请求管理员权限"}
    except Exception as e:
        logger.error(f"Error requesting admin restart: {e}")
        raise HTTPException(status_code=500, detail=f"请求管理员权限失败: {str(e)}")


# ==================== 捕获配置 API ====================

@router.get("/capture/config")
async def get_capture_config():
    """获取捕获配置"""
    try:
        # TODO: 实现获取捕获配置逻辑
        return {
            "capture_mode": "transparent",
            "use_windivert": False,
            "target_processes": [],
            "no_detection_timeout": 30,
            "log_unrecognized_domains": False
        }
    except Exception as e:
        logger.error(f"Error getting capture config: {e}")
        raise HTTPException(status_code=500, detail=f"获取捕获配置失败: {str(e)}")


@router.put("/capture/config")
async def update_capture_config(
    capture_mode: Optional[str] = Body(None),
    use_windivert: Optional[bool] = Body(None),
    target_processes: Optional[List[str]] = Body(None),
    no_detection_timeout: Optional[int] = Body(None),
    log_unrecognized_domains: Optional[bool] = Body(None)
):
    """更新捕获配置"""
    try:
        # TODO: 实现更新捕获配置逻辑
        return {"success": True, "message": "捕获配置已更新"}
    except Exception as e:
        logger.error(f"Error updating capture config: {e}")
        raise HTTPException(status_code=500, detail=f"更新捕获配置失败: {str(e)}")


@router.get("/capture/statistics")
async def get_capture_statistics():
    """获取捕获统计"""
    try:
        # TODO: 实现获取捕获统计逻辑
        return {
            "packets_captured": 0,
            "videos_detected": 0,
            "bytes_processed": 0
        }
    except Exception as e:
        logger.error(f"Error getting capture statistics: {e}")
        raise HTTPException(status_code=500, detail=f"获取捕获统计失败: {str(e)}")


@router.get("/diagnose")
async def diagnose_system():
    """诊断系统状态"""
    try:
        import ctypes
        import psutil
        
        # 检查管理员权限
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        
        # 检查微信进程
        wechat_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                name = proc.info['name']
                if name and any(x in name.lower() for x in ['wechat', 'weixin']):
                    wechat_processes.append({
                        'pid': proc.info['pid'],
                        'name': name,
                        'exe': proc.info['exe']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # 检查嗅探器状态
        sniffer = get_sniffer()
        sniffer_status = sniffer.get_status()
        
        # 检查端口占用
        port_available = True
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 8888))
        except OSError:
            port_available = False
        
        return {
            "is_admin": is_admin,
            "wechat_running": len(wechat_processes) > 0,
            "wechat_processes": wechat_processes,
            "sniffer_state": sniffer_status.state.value,
            "videos_detected": sniffer_status.videos_detected,
            "port_8888_available": port_available,
            "recommendations": _generate_recommendations(
                is_admin, 
                len(wechat_processes) > 0, 
                sniffer_status.state.value,
                sniffer_status.videos_detected
            )
        }
    except Exception as e:
        logger.error(f"Error diagnosing system: {e}")
        raise HTTPException(status_code=500, detail=f"诊断失败: {str(e)}")


def _generate_recommendations(is_admin: bool, wechat_running: bool, sniffer_state: str, videos_detected: int) -> list:
    """生成诊断建议"""
    recommendations = []
    
    if not is_admin:
        recommendations.append({
            "level": "error",
            "message": "应用未以管理员权限运行",
            "action": "请右键点击应用图标，选择\"以管理员身份运行\""
        })
    
    if not wechat_running:
        recommendations.append({
            "level": "warning",
            "message": "未检测到微信进程",
            "action": "请先启动 Windows PC 端微信"
        })
    
    if sniffer_state == "stopped":
        recommendations.append({
            "level": "info",
            "message": "嗅探器未启动",
            "action": "点击\"启动嗅探器\"按钮开始捕获视频"
        })
    elif sniffer_state == "running" and videos_detected == 0:
        recommendations.append({
            "level": "info",
            "message": "嗅探器已启动但未检测到视频",
            "action": "请在微信视频号中播放视频，系统会自动捕获视频链接"
        })
    
    if sniffer_state == "running" and videos_detected > 0:
        recommendations.append({
            "level": "success",
            "message": f"系统运行正常，已检测到 {videos_detected} 个视频",
            "action": "可以开始下载视频了"
        })
    
    return recommendations



