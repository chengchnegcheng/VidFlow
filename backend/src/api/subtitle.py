"""
字幕处理 API
"""
import asyncio
import json
import logging
import shlex
import uuid
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subtitle import SubtitleTask as SubtitleTaskModel, BurnSubtitleTask as BurnSubtitleTaskModel
from src.models.database import get_session, AsyncSessionLocal
from src.core.websocket_manager import get_ws_manager
from src.core.config_manager import get_config_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/subtitle", tags=["subtitle"])

_running_subtitle_tasks: Dict[str, asyncio.Task] = {}
_running_burn_subtitle_tasks: Dict[str, asyncio.Task] = {}

_subtitle_max_concurrent = 1
try:
    _subtitle_max_concurrent = int(get_config_manager().get("subtitle.max_concurrent", 1) or 1)
except Exception:
    _subtitle_max_concurrent = 1
_subtitle_semaphore = asyncio.Semaphore(max(1, _subtitle_max_concurrent))

_burn_max_concurrent = 1
try:
    _burn_max_concurrent = int(get_config_manager().get("subtitle.burn_max_concurrent", 1) or 1)
except Exception:
    _burn_max_concurrent = 1
_burn_semaphore = asyncio.Semaphore(max(1, _burn_max_concurrent))

class SubtitleGenerateRequest(BaseModel):
    video_path: str
    video_title: Optional[str] = None
    source_language: str = "auto"
    target_languages: List[str] = []
    model: str = "base"
    formats: List[str] = ["srt"]

class SubtitleTask(BaseModel):
    id: str
    video_path: str
    video_title: Optional[str]
    status: str
    progress: float
    source_language: str
    target_languages: List[str]
    model: str
    formats: List[str]
    output_files: List[str]
    error: Optional[str]
    error_detail: Optional[Dict[str, Any]] = None
    cancelled: bool = False
    detected_language: Optional[str]
    segments_count: int
    duration: float
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


def _validate_subtitle_path(path: Path) -> Path:
    """Validate subtitle path to avoid injection and unsupported formats."""
    dangerous_chars = ["'", '"', ";", "|", "&", "$", "`", "\n", "\r"]
    if any(char in str(path) for char in dangerous_chars):
        raise HTTPException(status_code=400, detail="字幕路径包含非法字符")

    allowed_extensions = {".srt", ".ass", ".ssa", ".vtt"}
    if path.suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=400, detail="不支持的字幕格式")

    if not path.exists():
        raise HTTPException(status_code=400, detail="字幕文件不存在")

    return path.resolve()


def _handle_task_exception(task: asyncio.Task):
    """记录后台任务异常，避免静默失败。"""
    try:
        exc = task.exception()
        if exc:
            logger.error(f"Background task failed: {exc}", exc_info=exc)
    except asyncio.CancelledError:
        logger.info("Background task was cancelled")
    except Exception as e:
        logger.error(f"Error handling task exception: {e}", exc_info=True)


def _truncate_message(message: str, limit: int = 2000) -> str:
    if not isinstance(message, str):
        try:
            message = str(message)
        except Exception:
            message = ""
    if len(message) <= limit:
        return message
    return message[:limit] + "..."


def _serialize_error(code: str, message: str, hint: Optional[str] = None) -> str:
    payload = {
        "code": code,
        "message": _truncate_message(message),
    }
    if hint:
        payload["hint"] = hint
    return json.dumps(payload, ensure_ascii=False)


def _serialize_subtitle_error(error: Exception) -> str:
    message = str(error)
    code = "SUBTITLE_TASK_FAILED"
    hint = "请重试，或查看日志获取更多信息"

    lowered = message.lower()
    if "faster-whisper" in lowered or "faster_whisper" in lowered or "torch" in lowered:
        code = "SUBTITLE_AI_TOOLS_MISSING"
        hint = "请到 设置→工具配置 安装 AI 工具"
    elif "ffmpeg" in lowered:
        code = "SUBTITLE_FFMPEG_MISSING"
        hint = "请到 设置→工具配置 安装 FFmpeg"
    elif "翻译" in message or "translation" in lowered or "translator" in lowered:
        code = "SUBTITLE_TRANSLATION_FAILED"
        hint = "请检查网络连接，或取消翻译后重试"

    return _serialize_error(code, message, hint)


def _serialize_burn_error(error: Exception) -> str:
    message = str(error)
    code = "BURN_SUBTITLE_TASK_FAILED"
    hint = "请重试，或查看日志获取更多信息"

    lowered = message.lower()
    if "ffmpeg" in lowered:
        code = "BURN_FFMPEG_FAILED"
        hint = "请确认 FFmpeg 已安装且可用"

    return _serialize_error(code, message, hint)

async def process_subtitle_task(task_id: str, request: SubtitleGenerateRequest):
    """后台处理字幕任务"""
    from src.core.subtitle_processor import get_subtitle_processor
    ws_manager = get_ws_manager()
    acquired = False
    try:
        await _subtitle_semaphore.acquire()
        acquired = True
        # 步骤1: 更新任务状态为处理中（短事务）
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SubtitleTaskModel).where(SubtitleTaskModel.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                logger.error(f"Task not found: {task_id}")
                return
            if getattr(task, "cancelled", False) or task.status == "cancelled":
                return
            
            task.status = "processing"
            task.started_at = datetime.utcnow()
            await db.commit()
            
        await ws_manager.send_subtitle_progress(
            task_id,
            {"progress": 0, "message": "开始处理...", "status": "processing"}
        )

        async def update_progress(progress: float, message: str = ""):
            try:
                async with AsyncSessionLocal() as db_inner:
                    result_inner = await db_inner.execute(
                        select(SubtitleTaskModel).where(SubtitleTaskModel.id == task_id)
                    )
                    task_inner = result_inner.scalar_one_or_none()
                    if not task_inner:
                        return
                    if getattr(task_inner, "cancelled", False) or task_inner.status == "cancelled":
                        raise asyncio.CancelledError()
                    task_inner.progress = round(progress, 1)
                    await db_inner.commit()
                await ws_manager.send_subtitle_progress(
                    task_id,
                    {
                        "progress": round(progress, 1),
                        "message": message,
                        "status": getattr(task_inner, "status", None),
                    }
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"Subtitle progress push failed: {e}")
        
        # 步骤2: 处理视频（不持有数据库连接）
        processor = get_subtitle_processor()
        video_path = Path(request.video_path)
        output_dir = video_path.parent / "subtitles"
        
        result_data = await processor.process_video(
            video_path=request.video_path,
            output_dir=str(output_dir),
            source_language=request.source_language,
            target_languages=request.target_languages,
            model_name=request.model,
            formats=request.formats,
            progress_callback=update_progress
        )
        
        # 步骤3: 更新任务为完成（短事务）
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SubtitleTaskModel).where(SubtitleTaskModel.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                logger.error(f"Task not found after processing: {task_id}")
                return
            if getattr(task, "cancelled", False) or task.status == "cancelled":
                return
            
            task.status = "completed"
            task.progress = 100.0
            task.output_files = result_data["output_files"]
            task.detected_language = result_data["language"]
            task.segments_count = result_data["segments_count"]
            task.duration = result_data["duration"]
            task.completed_at = datetime.utcnow()
            await db.commit()
            
            # 通知完成
            await ws_manager.broadcast({
                "type": "subtitle_task_complete",
                "data": {
                    "task_id": task_id,
                    "success": True,
                    "output_files": result_data["output_files"]
                }
            })
            
            logger.info(f"Subtitle task completed: {task_id}")
    
    except asyncio.CancelledError:
        logger.info(f"Subtitle task cancelled: {task_id}")
        send_updates = True
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(SubtitleTaskModel).where(SubtitleTaskModel.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    if task.status != "cancelled":
                        task.cancelled = True
                        task.status = "cancelled"
                        task.completed_at = datetime.utcnow()
                        await db.commit()
                    else:
                        send_updates = False
                else:
                    send_updates = False

            if send_updates:
                await ws_manager.send_subtitle_progress(
                    task_id,
                    {"progress": 0, "message": "已取消", "status": "cancelled"}
                )
                await ws_manager.broadcast({
                    "type": "subtitle_task_complete",
                    "data": {"task_id": task_id, "success": False, "cancelled": True}
                })
        except Exception as update_err:
            logger.error(f"Failed to update task status: {update_err}")

    except Exception as e:
        logger.error(f"Subtitle task failed: {e}", exc_info=True)

        serialized_error = _serialize_subtitle_error(e)
        
        # 更新任务为失败（短事务）
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(SubtitleTaskModel).where(SubtitleTaskModel.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error = serialized_error
                    task.completed_at = datetime.utcnow()
                    await db.commit()
                    
                    # 通知失败
                    await ws_manager.broadcast({
                        "type": "subtitle_task_complete",
                        "data": {
                            "task_id": task_id,
                            "success": False,
                            "error": serialized_error
                        }
                    })
        except Exception as update_err:
            logger.error(f"Failed to update task status: {update_err}")

    finally:
        if acquired:
            try:
                _subtitle_semaphore.release()
            except Exception:
                pass

@router.post("/generate", response_model=SubtitleTask)
async def generate_subtitle(
    request: SubtitleGenerateRequest,
    db: AsyncSession = Depends(get_session)
):
    """创建字幕生成任务"""
    try:
        # 检查文件是否存在
        video_path = Path(request.video_path)
        if not video_path.exists():
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "SUBTITLE_VIDEO_NOT_FOUND",
                    "message": "视频文件不存在",
                    "hint": "请检查文件路径是否正确",
                },
            )

        # 检查 AI 工具是否可用（缺失时直接提示，不进入后台静默失败）
        from src.core.tool_manager import get_tool_manager
        tool_mgr = get_tool_manager()
        ai_status = await tool_mgr.check_ai_tools_status()
        if not ai_status.get("python_compatible", True):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "SUBTITLE_PYTHON_INCOMPATIBLE",
                    "message": ai_status.get("error") or "Python 版本不兼容，无法使用字幕功能",
                    "hint": "请升级/切换 Python 版本，或重新安装应用",
                },
            )
        if not ai_status.get("installed", False):
            # 尽量给出可读原因
            missing = []
            if not ai_status.get("faster_whisper", False):
                missing.append("faster-whisper")
            if not ai_status.get("torch", False):
                missing.append("torch")
            missing_msg = "、".join(missing) if missing else "AI 组件"
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "SUBTITLE_AI_TOOLS_MISSING",
                    "message": f"AI 字幕组件未安装：{missing_msg}",
                    "hint": "请到 设置→工具配置 安装 AI 工具",
                },
            )
        
        # 创建任务模型
        task_id = str(uuid.uuid4())
        db_task = SubtitleTaskModel(
            id=task_id,
            video_path=request.video_path,
            video_title=request.video_title or video_path.stem,
            status="pending",
            progress=0.0,
            source_language=request.source_language,
            target_languages=request.target_languages,
            model=request.model,
            formats=request.formats,
            output_files=[],
            error=None,
            detected_language=None,
            segments_count=0,
            duration=0.0
        )
        
        # 保存到数据库
        db.add(db_task)
        await db.commit()
        await db.refresh(db_task)
        
        # 使用 asyncio.create_task 在后台处理（不阻塞事件循环）
        t = asyncio.create_task(process_subtitle_task(task_id, request))
        _running_subtitle_tasks[task_id] = t

        def _on_done(done: asyncio.Task):
            _running_subtitle_tasks.pop(task_id, None)
            _handle_task_exception(done)

        t.add_done_callback(_on_done)
        
        logger.info(f"Created subtitle task: {task_id}")
        
        return SubtitleTask(**db_task.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create subtitle task: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "SUBTITLE_TASK_CREATE_FAILED",
                "message": str(e),
                "hint": "请重试，或查看日志获取更多信息",
            },
        )

@router.get("/tasks")
async def get_subtitle_tasks(db: AsyncSession = Depends(get_session)):
    """获取所有字幕任务"""
    try:
        result = await db.execute(
            select(SubtitleTaskModel).order_by(SubtitleTaskModel.created_at.desc())
        )
        tasks = result.scalars().all()
        task_list = [task.to_dict() for task in tasks]
        return {
            "status": "success",
            "tasks": task_list,
            "total": len(task_list)
        }
    except Exception as e:
        logger.error(f"Failed to get tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{task_id}", response_model=SubtitleTask)
async def get_subtitle_task(task_id: str, db: AsyncSession = Depends(get_session)):
    """获取单个任务状态"""
    result = await db.execute(
        select(SubtitleTaskModel).where(SubtitleTaskModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SUBTITLE_TASK_NOT_FOUND",
                "message": "任务不存在",
                "hint": "请刷新任务列表",
            },
        )
    return SubtitleTask(**task.to_dict())

@router.post("/tasks/{task_id}/cancel")
async def cancel_subtitle_task(task_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(SubtitleTaskModel).where(SubtitleTaskModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SUBTITLE_TASK_NOT_FOUND",
                "message": "任务不存在",
                "hint": "请刷新任务列表",
            },
        )
    if task.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SUBTITLE_TASK_NOT_CANCELLABLE",
                "message": "任务已结束，无法取消",
                "hint": "已结束的任务可以直接删除",
            },
        )

    task.cancelled = True
    task.status = "cancelled"
    task.completed_at = datetime.utcnow()
    await db.commit()

    running = _running_subtitle_tasks.get(task_id)
    if running and not running.done():
        running.cancel()

    ws_manager = get_ws_manager()
    await ws_manager.send_subtitle_progress(
        task_id,
        {"progress": task.progress or 0, "message": "已取消", "status": "cancelled"}
    )
    await ws_manager.broadcast({
        "type": "subtitle_task_complete",
        "data": {"task_id": task_id, "success": False, "cancelled": True}
    })
    return {"success": True, "message": "任务取消中，请稍等..."}

@router.delete("/tasks/{task_id}")
async def delete_subtitle_task(task_id: str, db: AsyncSession = Depends(get_session)):
    """删除字幕任务"""
    result = await db.execute(
        select(SubtitleTaskModel).where(SubtitleTaskModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SUBTITLE_TASK_NOT_FOUND",
                "message": "任务不存在",
                "hint": "请刷新任务列表",
            },
        )
    
    await db.delete(task)
    await db.commit()
    return {"success": True, "message": "任务已删除"}

class BurnSubtitleRequest(BaseModel):
    video_path: str
    subtitle_path: str
    output_path: Optional[str] = None

@router.post("/burn-subtitle")
async def burn_subtitle_to_video(request: BurnSubtitleRequest):
    """将字幕烧录到视频中"""
    import subprocess
    from pathlib import Path
    
    try:
        video_file = Path(request.video_path)
        subtitle_file = Path(request.subtitle_path)
        subtitle_file = _validate_subtitle_path(subtitle_file)
        
        if not video_file.exists():
            raise HTTPException(status_code=400, detail="视频文件不存在")
        
        # 默认输出路径
        output_path = request.output_path
        if not output_path:
            output_path = str(video_file.parent / f"{video_file.stem}_subtitled{video_file.suffix}")
        
        # 获取 FFmpeg 路径
        from src.core.tool_manager import get_tool_manager
        tool_manager = get_tool_manager()
        ffmpeg_path = tool_manager.get_ffmpeg_path()
        
        if not ffmpeg_path:
            raise HTTPException(status_code=500, detail="FFmpeg 未安装")
        
        # 构建 FFmpeg 命令（使用 filter_complex 更安全）
        subtitle_path_escaped = str(subtitle_file).replace('\\', '\\\\').replace(':', '\\:')
        
        cmd = [
            str(ffmpeg_path),
            '-i', str(video_file),
            '-filter_complex', f"[0:v]subtitles={subtitle_path_escaped}[v]",
            '-map', '[v]',
            '-map', '0:a',
            '-c:a', 'copy',
            '-y',
            str(output_path)
        ]
        
        # 执行烧录
        logger.info(f"Burning subtitle: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"字幕烧录失败: {result.stderr}")
        
        logger.info(f"Subtitle burned successfully: {output_path}")
        
        return {
            "success": True,
            "output_path": output_path,
            "message": "字幕烧录完成"
        }
        
    except Exception as e:
        logger.error(f"Failed to burn subtitle: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
async def get_available_models():
    """获取可用的 Whisper 模型"""
    return {
        "models": [
            {
                "value": "tiny",
                "name": "Tiny",
                "description": "最快，精度较低",
                "size": "~75 MB"
            },
            {
                "value": "base",
                "name": "Base",
                "description": "推荐使用",
                "size": "~150 MB"
            },
            {
                "value": "small",
                "name": "Small",
                "description": "较慢，精度较高",
                "size": "~500 MB"
            },
            {
                "value": "medium",
                "name": "Medium",
                "description": "慢，高精度",
                "size": "~1.5 GB"
            },
            {
                "value": "large",
                "name": "Large",
                "description": "最慢，最高精度",
                "size": "~2.9 GB"
            }
        ]
    }

@router.get("/languages")
async def get_supported_languages():
    """获取支持的语言"""
    return {
        "languages": [
            {"code": "auto", "name": "自动检测"},
            {"code": "zh", "name": "中文"},
            {"code": "en", "name": "English"},
            {"code": "ja", "name": "日本語"},
            {"code": "ko", "name": "한국어"},
            {"code": "es", "name": "Español"},
            {"code": "fr", "name": "Français"},
            {"code": "de", "name": "Deutsch"},
            {"code": "ru", "name": "Русский"},
            {"code": "ar", "name": "العربية"},
            {"code": "pt", "name": "Português"},
            {"code": "it", "name": "Italiano"}
        ]
    }


# ==================== 烧录字幕任务管理 ====================

class CreateBurnSubtitleTaskRequest(BaseModel):
    video_path: str
    subtitle_path: str
    output_path: Optional[str] = None
    video_title: Optional[str] = None


async def process_burn_subtitle_task(task_id: str, request: CreateBurnSubtitleTaskRequest):
    """后台处理烧录字幕任务"""
    from src.models.database import AsyncSessionLocal
    import subprocess
    import json
    import math

    ws_manager = get_ws_manager()
    acquired = False
    process: Optional[asyncio.subprocess.Process] = None
    try:
        await _burn_semaphore.acquire()
        acquired = True

        async with AsyncSessionLocal() as db:
            try:
                # 从数据库获取任务
                result = await db.execute(
                    select(BurnSubtitleTaskModel).where(BurnSubtitleTaskModel.id == task_id)
                )
                task = result.scalar_one_or_none()
                if not task:
                    logger.error(f"Burn task not found: {task_id}")
                    return

                if getattr(task, "cancelled", False) or task.status == "cancelled":
                    return

                # 更新状态为烧录中
                task.status = "burning"
                task.started_at = datetime.utcnow()
                await db.commit()

                # WebSocket 通知
                await ws_manager.broadcast({
                    "type": "burn_subtitle_task_update",
                    "data": task.to_dict()
                })

                # 获取 FFmpeg 路径
                from src.core.tool_manager import get_tool_manager
                tool_manager = get_tool_manager()
                ffmpeg_path = tool_manager.get_ffmpeg_path()

                if not ffmpeg_path:
                    raise Exception("FFmpeg 未安装")

                # 校验字幕路径
                subtitle_path = _validate_subtitle_path(Path(request.subtitle_path))
                
                # 关键修复：使用相对路径 + cwd 避免 Windows 路径转义地狱
                # FFmpeg 的 subtitles 滤镜对 Windows 绝对路径（如 D:\path）处理非常麻烦
                # 最稳健的方法是：cd 到字幕目录，然后只传文件名
                subtitle_dir = subtitle_path.parent
                subtitle_filename = subtitle_path.name
                
                # 对文件名进行基本的 FFmpeg 转义（防止文件名含单引号等）
                # filter 语法中: ' 需要转义为 '\''
                # : 需要转义为 \:
                subtitle_filename_escaped = subtitle_filename.replace("'", r"'\''").replace(":", r"\:")

                cmd = [
                    str(ffmpeg_path),
                    '-i', str(request.video_path),
                    '-vf', f"subtitles='{subtitle_filename_escaped}'",
                    '-c:a', 'copy',
                    '-y',
                    str(task.output_path)
                ]

                # ... (中间代码省略)

                # 执行烧录（设置 cwd 为字幕目录）
                logger.info(f"Burning subtitle (cwd={subtitle_dir}): {' '.join(cmd)}")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(subtitle_dir)  # 关键：设置工作目录
                )

                time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    text = line.decode(errors="ignore").strip()
                    match = time_pattern.search(text)
                    if match and duration:
                        h, m, s = match.groups()
                        current_time = int(h) * 3600 + int(m) * 60 + float(s)
                        progress = round(min(current_time / duration * 100, 99.0), 1)
                        task.progress = progress
                        await db.commit()
                        await ws_manager.send_burn_progress(task_id, {
                            "progress": progress,
                            "current": current_time,
                            "duration": duration,
                            "status": "burning"
                        })

                await process.wait()

                if process.returncode != 0:
                    stderr_full = await process.stderr.read()
                    raise Exception(f"FFmpeg error: {stderr_full.decode(errors='ignore')}")

                # 更新任务为完成
                task.status = "completed"
                task.progress = 100.0
                task.completed_at = datetime.utcnow()
                await db.commit()

                # 通知完成
                await ws_manager.broadcast({
                    "type": "burn_subtitle_task_complete",
                    "data": {
                        "task_id": task_id,
                        "success": True,
                        "output_path": task.output_path
                    }
                })

                logger.info(f"Burn subtitle task completed: {task_id}")

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Burn subtitle task failed: {e}", exc_info=True)

                serialized_error = _serialize_burn_error(e)

                # 更新任务为失败
                result = await db.execute(
                    select(BurnSubtitleTaskModel).where(BurnSubtitleTaskModel.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error = serialized_error
                    task.completed_at = datetime.utcnow()
                    await db.commit()

                    # 通知失败
                    await ws_manager.broadcast({
                        "type": "burn_subtitle_task_complete",
                        "data": {
                            "task_id": task_id,
                            "success": False,
                            "error": serialized_error
                        }
                    })

    except asyncio.CancelledError:
        logger.info(f"Burn subtitle task cancelled: {task_id}")
        send_updates = True
        cancel_progress = 0
        try:
            if process and process.returncode is None:
                try:
                    process.terminate()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
                    try:
                        await process.wait()
                    except Exception:
                        pass

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(BurnSubtitleTaskModel).where(BurnSubtitleTaskModel.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    cancel_progress = task.progress or 0
                    if task.status != "cancelled":
                        task.cancelled = True
                        task.status = "cancelled"
                        task.completed_at = datetime.utcnow()
                        await db.commit()
                    else:
                        send_updates = False
                else:
                    send_updates = False

            if send_updates:
                await ws_manager.send_burn_progress(
                    task_id,
                    {"progress": cancel_progress, "status": "cancelled"}
                )
                await ws_manager.broadcast({
                    "type": "burn_subtitle_task_complete",
                    "data": {"task_id": task_id, "success": False, "cancelled": True}
                })
        except Exception as update_err:
            logger.error(f"Failed to update burn task status: {update_err}", exc_info=True)

    finally:
        if acquired:
            try:
                _burn_semaphore.release()
            except Exception:
                pass


@router.post("/burn-subtitle-task")
async def create_burn_subtitle_task(
    request: CreateBurnSubtitleTaskRequest,
    db: AsyncSession = Depends(get_session)
):
    """创建字幕烧录任务"""
    try:
        # 检查文件是否存在
        video_path = Path(request.video_path)
        subtitle_path = Path(request.subtitle_path)
        if not video_path.exists():
            raise HTTPException(status_code=400, detail="视频文件不存在")
        if not subtitle_path.exists():
            raise HTTPException(status_code=400, detail="字幕文件不存在")
        
        # 默认输出路径
        output_path = request.output_path
        if not output_path:
            output_path = str(video_path.parent / f"{video_path.stem}_subtitled{video_path.suffix}")
        
        # 创建任务模型
        task_id = str(uuid.uuid4())
        db_task = BurnSubtitleTaskModel(
            id=task_id,
            video_path=request.video_path,
            subtitle_path=request.subtitle_path,
            output_path=output_path,
            video_title=request.video_title or video_path.stem,
            status="pending",
            progress=0.0
        )
        
        # 保存到数据库
        db.add(db_task)
        await db.commit()
        await db.refresh(db_task)
        
        # 使用 asyncio.create_task 在后台处理（不阻塞事件循环）
        t = asyncio.create_task(process_burn_subtitle_task(task_id, request))
        _running_burn_subtitle_tasks[task_id] = t

        def _on_done(done: asyncio.Task):
            _running_burn_subtitle_tasks.pop(task_id, None)
            _handle_task_exception(done)

        t.add_done_callback(_on_done)
        
        logger.info(f"Created burn subtitle task: {task_id}")
        
        return db_task.to_dict()
        
    except Exception as e:
        logger.error(f"Failed to create burn subtitle task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/burn-subtitle-tasks")
async def get_burn_subtitle_tasks(db: AsyncSession = Depends(get_session)):
    """获取所有烧录任务"""
    try:
        result = await db.execute(
            select(BurnSubtitleTaskModel).order_by(BurnSubtitleTaskModel.created_at.desc())
        )
        tasks = result.scalars().all()
        task_list = [task.to_dict() for task in tasks]
        return task_list
    except Exception as e:
        logger.error(f"Failed to get burn tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/burn-subtitle-tasks/{task_id}/cancel")
async def cancel_burn_subtitle_task(task_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(BurnSubtitleTaskModel).where(BurnSubtitleTaskModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "BURN_SUBTITLE_TASK_NOT_FOUND",
                "message": "任务不存在",
                "hint": "请刷新任务列表",
            },
        )

    if task.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BURN_SUBTITLE_TASK_NOT_CANCELLABLE",
                "message": "任务已结束，无法取消",
                "hint": "已结束的任务可以直接删除",
            },
        )

    task.cancelled = True
    task.status = "cancelled"
    task.completed_at = datetime.utcnow()
    await db.commit()

    running = _running_burn_subtitle_tasks.get(task_id)
    if running and not running.done():
        running.cancel()

    ws_manager = get_ws_manager()
    await ws_manager.send_burn_progress(
        task_id,
        {"progress": task.progress or 0, "status": "cancelled"}
    )
    await ws_manager.broadcast({
        "type": "burn_subtitle_task_complete",
        "data": {"task_id": task_id, "success": False, "cancelled": True}
    })
    return {"success": True, "message": "任务取消中，请稍等..."}


@router.delete("/burn-subtitle-tasks/{task_id}")
async def delete_burn_subtitle_task(task_id: str, db: AsyncSession = Depends(get_session)):
    """删除烧录任务"""
    result = await db.execute(
        select(BurnSubtitleTaskModel).where(BurnSubtitleTaskModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    await db.delete(task)
    await db.commit()
    return {"success": True, "message": "任务已删除"}
