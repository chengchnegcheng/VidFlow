"""
频道视频捕获和下载 API
"""
import logging
import os
import re
import shutil
import sys
import asyncio
import time
import uuid
import hashlib
from collections import deque
from functools import lru_cache
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import FileResponse, Response
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from pathlib import Path
from sqlalchemy import desc, or_, select
from urllib.parse import parse_qs, urlparse

from ..core.channels.proxy_sniffer import ProxySniffer, LOCAL_MODE_TARGET_PROCESSES
from ..core.channels.process_targets import (
    CORE_WECHAT_PROCESS_NAMES,
    CHANNELS_BROWSER_HELPER_PROCESS_NAMES,
    resolve_local_capture_processes,
)
from ..core.channels.platform_detector import PlatformDetector
from ..core.channels.proxy_detector import ProxyDetector
from ..core.channels.driver_manager import DriverManager
from ..core.channels.models import (
    CaptureConfig,
    CaptureMode,
    DetectedVideo,
    DriverState,
    EncryptionType,
    ProxyInfo,
    ProxyMode,
)
from ..core.downloaders.channels_downloader import ChannelsDownloader
from ..models import DownloadTask
from ..models.database import AsyncSessionLocal, get_data_dir
from .proxy import proxy_image as shared_proxy_image

router = APIRouter(prefix="/api/channels", tags=["channels"])
logger = logging.getLogger(__name__)

# 全局实例
_sniffer: Optional[ProxySniffer] = None
_downloader: Optional[ChannelsDownloader] = None
_driver_manager: Optional[DriverManager] = None
_proxy_detector: Optional[ProxyDetector] = None
_cert_installer = None
_system_proxy_manager = None
_system_proxy_enabled = False
_active_proxy_port: Optional[int] = None
_download_tasks: Dict[str, asyncio.Task[Any]] = {}
_last_video_list_snapshot: Optional[str] = None
_capture_config = CaptureConfig(
    capture_mode=CaptureMode.TRANSPARENT,
    use_windivert=True,
)
_runtime_config = {
    "proxy_port": 8888,
    "download_dir": "",
    "auto_decrypt": True,
    "auto_clean_wechat_cache": True,
    "quality_preference": "best",
    "clear_on_exit": False,
}
_CHANNEL_TASK_PLATFORMS = {"weixin_channels", "wechat_channels", "channels"}
_CHANNEL_TASK_STATUSES = {"pending", "downloading", "decrypting", "completed", "encrypted", "failed", "cancelled"}
_LEGACY_DEFAULT_TARGET_PROCESSES = {"WeChat.exe", "WeChatAppEx.exe"}
_PREVIOUS_DEFAULT_TARGET_PROCESSES = {
    process.lower()
    for process in (CORE_WECHAT_PROCESS_NAMES + CHANNELS_BROWSER_HELPER_PROCESS_NAMES)
}
_DEFAULT_WECHAT_CORE_PROCESS_SET = {
    process.lower() for process in CORE_WECHAT_PROCESS_NAMES
}
_HELPER_PROCESS_HINT = "、".join(CHANNELS_BROWSER_HELPER_PROCESS_NAMES)
_HELPER_PROCESS_NAME_SET = {
    process.lower() for process in CHANNELS_BROWSER_HELPER_PROCESS_NAMES
}
_CHANNELS_DIAGNOSTIC_LOG_MARKERS = (
    "src.core.channels.proxy_sniffer",
    "src.api.channels",
    "mitmproxy.shutdown",
    "[MMTLS]",
    "[META]",
    "Injected VidFlow",
    "redirect daemon exited prematurely",
    "Starting mitmproxy in local mode",
    "allow_hosts=",
    "Channels proxy bridge request",
    "Injected channels metadata accepted",
    "Injected channels metadata cached via proxy without URL",
    "Raw server TCP stream produced no metadata yet",
    "Cached metadata from binary response",
)
_CHANNELS_DIAGNOSTIC_CRITICAL_MARKERS = (
    "redirect daemon exited prematurely",
    "Task failed:",
    "Binary metadata miss",
    "contained channels markers but no complete metadata",
    "Raw server TCP stream produced no metadata yet",
)
_CERTIFICATE_EXPORT_EXTENSIONS = {
    "cer": {".cer", ".crt", ".pem"},
    "p12": {".p12", ".pfx"},
}


class _LegacyChannelsConfigProxy:
    """Expose the old attribute-style config API on top of the runtime config dict."""

    _fields = {
        "proxy_port",
        "download_dir",
        "auto_decrypt",
        "auto_clean_wechat_cache",
        "quality_preference",
        "clear_on_exit",
    }

    def __getattr__(self, name: str) -> Any:
        if name in self._fields:
            return _runtime_config.get(name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_fields":
            super().__setattr__(name, value)
            return
        if name in self._fields:
            _runtime_config[name] = value
            return
        raise AttributeError(name)

    def to_dict(self) -> Dict[str, Any]:
        return dict(_runtime_config)


_config = _LegacyChannelsConfigProxy()
_cert_manager = None


@lru_cache(maxsize=1)
def _load_inject_script() -> str:
    """Load the WeChat Channels injection script from disk."""
    script_path = Path(__file__).resolve().parent.parent / "core" / "channels" / "inject_script.js"
    return script_path.read_text(encoding="utf-8")


def _normalize_decode_key(value: Optional[str]) -> Optional[str]:
    """仅保留数字 decodeKey。"""
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate if candidate.isdigit() else None


def _validate_certificate_export_target(export_path: str, cert_format: str) -> Path:
    """Restrict certificate exports to user-owned locations with expected file types."""
    if not export_path or not isinstance(export_path, str):
        raise HTTPException(status_code=400, detail="导出路径不能为空")

    allowed_extensions = _CERTIFICATE_EXPORT_EXTENSIONS.get(cert_format)
    if not allowed_extensions:
        raise HTTPException(status_code=400, detail="不支持的证书格式")

    target = Path(export_path).expanduser()
    if not target.name:
        raise HTTPException(status_code=400, detail="导出路径必须包含文件名")

    if target.suffix.lower() not in allowed_extensions:
        expected = "、".join(sorted(allowed_extensions))
        raise HTTPException(status_code=400, detail=f"导出文件扩展名必须为: {expected}")

    try:
        target_parent = target.parent.resolve()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="导出目录无效") from exc

    if not target_parent.exists() or not target_parent.is_dir():
        raise HTTPException(status_code=400, detail="导出目录不存在")

    allowed_roots = [Path.home().expanduser().resolve()]
    onedrive_root = os.environ.get("OneDrive")
    if onedrive_root:
        try:
            allowed_roots.append(Path(onedrive_root).expanduser().resolve())
        except Exception:
            pass

    def _is_within_root(root: Path) -> bool:
        if target_parent == root:
            return True
        try:
            target_parent.relative_to(root)
            return True
        except ValueError:
            return False

    if not any(_is_within_root(root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="只允许导出到当前用户目录")

    return target_parent / target.name


def _normalize_task_status(status: Optional[str]) -> str:
    """归一化任务状态，避免前端收到未知值。"""
    if status in _CHANNEL_TASK_STATUSES:
        return status  # type: ignore[return-value]
    if status == "paused":
        return "pending"
    return "pending"


def _task_to_channels_payload(task: DownloadTask) -> Dict[str, Any]:
    """将下载任务模型转换为频道页任务结构。"""
    data = task.to_dict()
    created_at = int(task.created_at.timestamp()) if task.created_at else int(time.time())

    return {
        "task_id": data.get("task_id"),
        "url": data.get("url"),
        "title": data.get("title") or "微信视频号视频",
        "thumbnail": data.get("thumbnail"),
        "status": _normalize_task_status(data.get("status")),
        "progress": float(data.get("progress") or 0),
        "speed": float(data.get("speed") or 0),
        "downloaded": int(data.get("downloaded_bytes") or 0),
        "total": int(data.get("total_bytes") or 0),
        "file_path": data.get("file_path"),
        "error": data.get("error_message"),
        "created_at": created_at,
    }


def _resolve_detected_video(url: str):
    """Resolve the latest detected video entry for a normalized channels URL."""
    try:
        normalized_url = ChannelsDownloader._normalize_video_url(url)
        sniffer = get_sniffer()
        videos = sniffer.get_detected_videos()
        requested_cache_keys = set(sniffer._build_metadata_cache_keys(normalized_url))
        fallback_video = None
        for video in reversed(videos):
            candidate_url = ChannelsDownloader._normalize_video_url(video.url)
            if candidate_url == normalized_url:
                return _normalize_detected_video_for_display(sniffer, video) or video

            if fallback_video is None and requested_cache_keys:
                candidate_cache_keys = set(sniffer._build_metadata_cache_keys(candidate_url))
                if candidate_cache_keys.intersection(requested_cache_keys):
                    fallback_video = _normalize_detected_video_for_display(sniffer, video) or video
        if fallback_video is not None:
            return fallback_video
    except Exception:
        logger.debug("Failed to resolve channels video from sniffer cache", exc_info=True)
    return None


def _resolve_task_title(url: str) -> str:
    """尽量复用嗅探到的视频标题。"""
    video = _resolve_detected_video(url)
    if video:
        sniffer = get_sniffer()
        sanitized_title = sniffer._sanitize_video_title(getattr(video, "title", None))
        if sanitized_title:
            return sanitized_title

        try:
            normalized_url = ChannelsDownloader._normalize_video_url(url)
            query_params = parse_qs(urlparse(normalized_url).query)
            fallback_id = PlatformDetector.extract_video_id(normalized_url) or str(getattr(video, "id", "") or "").strip()
            if fallback_id:
                return sniffer._build_fallback_title(fallback_id, query_params)
        except Exception:
            logger.debug("Failed to build fallback task title", exc_info=True)
    return "微信视频号视频"


def _requires_decode_key(url: str, detected_video: Optional[Any] = None) -> bool:
    """Return True when the channels payload is encrypted and needs decodeKey."""
    normalized_url = ChannelsDownloader._normalize_video_url(url)
    lower_url = normalized_url.lower()
    if "encfilekey=" in lower_url or "/stodownload" in lower_url:
        return True

    encryption_type = getattr(detected_video, "encryption_type", None)
    if getattr(encryption_type, "value", encryption_type) == "isaac64":
        return True

    return False


def _is_fallback_channels_title(title: Optional[str]) -> bool:
    """Detect generated placeholder titles like channels_177279598807."""
    value = str(title or "").strip()
    if not value:
        return True
    return re.fullmatch(r"channels_[A-Za-z0-9_-]{6,}", value, re.IGNORECASE) is not None


def _normalize_identity_text(value: Optional[Any]) -> str:
    """Normalize user-facing metadata for fuzzy identity matching."""
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _extract_query_value(query_params: Dict[str, List[str]], *names: str) -> Optional[str]:
    """Return the first non-empty query parameter value."""
    for name in names:
        values = query_params.get(name)
        if not values:
            continue
        for value in values:
            candidate = str(value or "").strip()
            if candidate:
                return candidate
    return None


def _build_thumbnail_identity(thumbnail: Optional[str]) -> str:
    """Build a coarse thumbnail fingerprint without relying on rotating tokens."""
    raw_value = str(thumbnail or "").strip()
    if not raw_value:
        return ""

    try:
        parsed = urlparse(raw_value)
        query_params = parse_qs(parsed.query)
        idx = _extract_query_value(query_params, "idx")
        pic_format = _extract_query_value(query_params, "picformat", "wxampicformat")
        parts = [str(parsed.hostname or "").lower(), parsed.path.lower()]
        if idx:
            parts.append(f"idx={idx}")
        if pic_format:
            parts.append(f"pic={pic_format}")
        return "|".join(part for part in parts if part)
    except Exception:
        return raw_value


def _build_channels_item_identity(
    *,
    url: Optional[str],
    title: Optional[str],
    duration: Optional[int],
    resolution: Optional[str],
    filesize: Optional[int],
    thumbnail: Optional[str],
    decryption_key: Optional[str],
) -> str:
    """Build a stable identity for channels videos/tasks across rotating URLs."""
    normalized_url = ChannelsDownloader._normalize_video_url(str(url or "").strip())
    try:
        parsed = urlparse(normalized_url)
        query_params = parse_qs(parsed.query)
    except Exception:
        parsed = urlparse("")
        query_params = {}

    for names in (
        ("objectid", "objectId"),
        ("feedid", "feedId"),
    ):
        stable_value = _extract_query_value(query_params, *names)
        if stable_value:
            return f"{names[0]}:{stable_value}"

    title_key = _normalize_identity_text(title)
    title_is_stable = bool(title_key) and not _is_fallback_channels_title(title)
    resolution_key = _normalize_identity_text(resolution)
    thumbnail_key = _build_thumbnail_identity(thumbnail)
    decode_key = _normalize_decode_key(decryption_key)
    filesize_value = int(filesize or 0)

    if title_is_stable and thumbnail_key:
        metadata_fingerprint = "|".join(
            [
                title_key,
                thumbnail_key,
            ]
        )
        return f"meta-thumb:{hashlib.md5(metadata_fingerprint.encode('utf-8')).hexdigest()}"

    if title_is_stable and any(
        (
            duration is not None,
            resolution_key,
            thumbnail_key,
        )
    ):
        metadata_fingerprint = "|".join(
            [
                title_key,
                str(duration or ""),
                resolution_key,
                thumbnail_key,
            ]
        )
        return f"meta:{hashlib.md5(metadata_fingerprint.encode('utf-8')).hexdigest()}"

    if title_is_stable and filesize_value > 0:
        title_filesize_fingerprint = f"{title_key}|{filesize_value}"
        return f"title-size:{hashlib.md5(title_filesize_fingerprint.encode('utf-8')).hexdigest()}"

    if decode_key and any((duration is not None, resolution_key, thumbnail_key)):
        decode_fingerprint = "|".join([decode_key, str(duration or ""), resolution_key, thumbnail_key])
        return f"decode:{hashlib.md5(decode_fingerprint.encode('utf-8')).hexdigest()}"

    task_value = _extract_query_value(query_params, "taskid", "taskId")
    if task_value:
        return f"taskid:{task_value}"

    return PlatformDetector.extract_video_id(normalized_url) or normalized_url or parsed.path or "channels"


def _preview_log_value(value: Optional[Any], limit: int = 96) -> str:
    """Build a compact single-line preview for diagnostic logs."""
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return "-"
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _collect_video_placeholder_reasons(video: Any) -> List[str]:
    """Return stable placeholder reason codes for detected videos."""
    reasons: List[str] = []
    if _requires_decode_key(video.url, video) and not _normalize_decode_key(video.decryption_key):
        reasons.append("missing_decode_key")
    if _is_fallback_channels_title(video.title):
        reasons.append("missing_title")
    if not bool(video.thumbnail):
        reasons.append("missing_thumbnail")
    return reasons


def _log_display_video_snapshot(videos: List[DetectedVideo]) -> None:
    """Emit a one-shot log when the merged /videos snapshot changes."""
    global _last_video_list_snapshot

    if not videos:
        snapshot = "empty"
        if snapshot == _last_video_list_snapshot:
            return
        _last_video_list_snapshot = snapshot
        logger.info("Channels display snapshot updated: empty")
        return

    snapshot_entries: List[str] = []
    for index, video in enumerate(videos, start=1):
        merge_key = _build_channels_item_identity(
            url=video.url,
            title=video.title,
            duration=video.duration,
            resolution=video.resolution,
            filesize=video.filesize,
            thumbnail=video.thumbnail,
            decryption_key=video.decryption_key,
        )
        placeholder_reasons = _collect_video_placeholder_reasons(video)
        snapshot_entries.append(
            "|".join(
                [
                    str(index),
                    merge_key,
                    ChannelsDownloader._normalize_video_url(str(video.url or "").strip()),
                    _normalize_decode_key(video.decryption_key) or "",
                    ",".join(placeholder_reasons),
                    str(video.duration or ""),
                    str(video.resolution or ""),
                    str(video.thumbnail or ""),
                    str(video.title or ""),
                ]
            )
        )
    snapshot = "\n".join(snapshot_entries)
    if snapshot == _last_video_list_snapshot:
        return

    _last_video_list_snapshot = snapshot
    logger.info("Channels display snapshot updated: %s item(s)", len(videos))
    for index, video in enumerate(videos, start=1):
        merge_key = _build_channels_item_identity(
            url=video.url,
            title=video.title,
            duration=video.duration,
            resolution=video.resolution,
            filesize=video.filesize,
            thumbnail=video.thumbnail,
            decryption_key=video.decryption_key,
        )
        placeholder_reasons = _collect_video_placeholder_reasons(video)
        logger.info(
            "  [%s] mergeKey=%s decodeKey=%s requiresKey=%s placeholder=%s reasons=%s enc=%s duration=%s resolution=%s title=%s url=%s",
            index,
            _preview_log_value(merge_key, 48),
            "yes" if _normalize_decode_key(video.decryption_key) else "no",
            "yes" if _requires_decode_key(video.url, video) else "no",
            "yes" if placeholder_reasons else "no",
            ",".join(placeholder_reasons) or "-",
            str(getattr(video, "encryption_type", None) or "unknown"),
            str(video.duration or "-"),
            _preview_log_value(video.resolution, 24),
            _preview_log_value(video.title, 72),
            _preview_log_value(video.url, 144),
        )


def _pick_preferred_task_title(current: Optional[str], incoming: Optional[str]) -> Optional[str]:
    """Prefer non-placeholder titles when deduplicating download tasks."""
    current_value = str(current or "").strip()
    incoming_value = str(incoming or "").strip()
    if incoming_value and _is_fallback_channels_title(current_value) and not _is_fallback_channels_title(incoming_value):
        return incoming_value
    return current_value or incoming_value or None


def _get_wechat_channels_cache_dir() -> Optional[Path]:
    """Return the WeChat desktop webview profile cache used by Channels pages."""
    if not sys.platform.startswith("win"):
        return None

    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None

    return Path(appdata) / "Tencent" / "WeChat" / "radium" / "web" / "profiles"


def _clear_directory_contents(target_dir: Path) -> Dict[str, Any]:
    """Clear all children inside a directory while keeping the root directory."""
    removed_entries = 0
    failed_entries: List[str] = []

    if not target_dir.exists():
        return {"removed_entries": 0, "failed_entries": failed_entries}

    for child in list(target_dir.iterdir()):
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed_entries += 1
        except FileNotFoundError:
            continue
        except Exception:
            failed_entries.append(child.name)
            logger.debug("Failed to remove WeChat cache entry: %s", child, exc_info=True)

    return {
        "removed_entries": removed_entries,
        "failed_entries": failed_entries,
    }


def _auto_prepare_wechat_channels_cache(sniffer: ProxySniffer) -> Dict[str, Any]:
    """Refresh WeChat renderers and clear stale Channels web cache before capture."""
    result: Dict[str, Any] = {
        "enabled": bool(_runtime_config.get("auto_clean_wechat_cache", True)),
        "cache_dir": None,
        "removed_entries": 0,
        "failed_entries": [],
        "recycled_renderers": [],
        "message": None,
    }
    if not result["enabled"]:
        return result

    cache_dir = _get_wechat_channels_cache_dir()
    if cache_dir is None:
        return result

    result["cache_dir"] = str(cache_dir)
    if not cache_dir.exists():
        return result

    recycled_renderers: List[str] = []
    recycle_method = getattr(sniffer, "_recycle_wechat_renderer_processes", None)
    if callable(recycle_method):
        try:
            recycled_renderers = list(recycle_method(force_helpers=True) or [])
        except Exception:
            logger.debug("Failed to recycle WeChat renderer processes before cache cleanup", exc_info=True)
    result["recycled_renderers"] = recycled_renderers

    cleanup_result = _clear_directory_contents(cache_dir)
    result["removed_entries"] = int(cleanup_result.get("removed_entries") or 0)
    result["failed_entries"] = list(cleanup_result.get("failed_entries") or [])

    if result["removed_entries"] > 0:
        details: List[str] = [f"已自动清理微信视频号缓存（{result['removed_entries']}项）"]
        if recycled_renderers:
            details.append(f"并刷新页面进程（{len(recycled_renderers)}个）")
        result["message"] = "，".join(details) + "。请重新打开视频号页面并完整播放目标视频一次。"
    elif result["failed_entries"]:
        details = ["自动清理微信视频号缓存未完全成功"]
        if recycled_renderers:
            details.append(f"已刷新页面进程（{len(recycled_renderers)}个）")
        result["message"] = "，".join(details) + "。请完全退出微信后重试。"
    elif recycled_renderers:
        result["message"] = f"已自动刷新微信页面进程（{len(recycled_renderers)}个）。请重新打开视频号页面并完整播放目标视频一次。"

    return result


def _coerce_encryption_type(value: Any) -> EncryptionType:
    raw_value = getattr(value, "value", value)
    if isinstance(raw_value, EncryptionType):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return EncryptionType(raw_value)
        except ValueError:
            return EncryptionType.UNKNOWN
    return EncryptionType.UNKNOWN


def _get_cached_channels_metadata(sniffer: ProxySniffer, url: Optional[str]):
    """Resolve cached channels metadata by URL-derived cache keys."""
    normalized_url = ChannelsDownloader._normalize_video_url(str(url or "").strip())
    if not normalized_url:
        return None

    try:
        cache_keys = sniffer._build_metadata_cache_keys(normalized_url)
        return sniffer._merge_cached_metadata(cache_keys)
    except Exception:
        logger.debug("Failed to resolve cached channels metadata for %s", normalized_url[:120], exc_info=True)
        return None


def _normalize_detected_video_for_display(sniffer: ProxySniffer, video: Any) -> Optional[DetectedVideo]:
    raw_url = str(getattr(video, "url", "") or "").strip()
    if not raw_url:
        return None

    normalized_url = ChannelsDownloader._normalize_video_url(raw_url)
    parsed = urlparse(normalized_url)
    query_params = parse_qs(parsed.query)

    video_id = (
        PlatformDetector.extract_video_id(normalized_url)
        or str(getattr(video, "id", "") or "").strip()
        or hashlib.md5(normalized_url.encode("utf-8")).hexdigest()[:16]
    )
    cached_metadata = _get_cached_channels_metadata(sniffer, normalized_url)
    title = sniffer._pick_better_title(
        sniffer._sanitize_video_title(getattr(video, "title", None)),
        getattr(cached_metadata, "title", None),
    )
    if not title:
        title = sniffer._build_fallback_title(video_id, query_params)

    thumbnail = (
        sniffer._extract_thumbnail_url(getattr(video, "thumbnail", None))
        or getattr(cached_metadata, "thumbnail", None)
    )
    # decodeKey 不能从缓存借用！每个画质/URL 有独立的加密密钥，
    # 缓存中的 decodeKey 可能属于另一个画质的 URL，借用会导致解密失败。
    decryption_key = sniffer._normalize_decode_key(getattr(video, "decryption_key", None))
    duration = getattr(video, "duration", None)
    if duration is None:
        duration = getattr(cached_metadata, "duration", None)
    resolution = getattr(video, "resolution", None) or getattr(cached_metadata, "resolution", None)
    filesize = getattr(video, "filesize", None)
    if filesize is None:
        filesize = getattr(cached_metadata, "filesize", None)
    encryption_type = _coerce_encryption_type(getattr(video, "encryption_type", None))
    if encryption_type == EncryptionType.UNKNOWN:
        encryption_type = sniffer._infer_encryption_type(normalized_url, decryption_key)

    detected_at = getattr(video, "detected_at", None)
    if not isinstance(detected_at, datetime):
        detected_at = datetime.now()

    return DetectedVideo(
        id=video_id,
        url=normalized_url,
        title=title,
        duration=duration,
        resolution=resolution,
        filesize=filesize,
        thumbnail=thumbnail,
        detected_at=detected_at,
        encryption_type=encryption_type,
        decryption_key=decryption_key,
    )


def _merge_display_videos(sniffer: ProxySniffer, current: DetectedVideo, incoming: DetectedVideo) -> DetectedVideo:
    preferred_title = sniffer._pick_better_title(current.title, incoming.title) or current.title or incoming.title

    # URL 和 decodeKey 必须配对：每个画质有独立的加密密钥，
    # 所以必须选取"自带 decodeKey 的那个 URL"，而不是随意组合。
    current_has_own_key = bool(current.decryption_key and current.url)
    incoming_has_own_key = bool(incoming.decryption_key and incoming.url)
    current_taskid = ProxySniffer._extract_taskid(current.url) if current.url else None
    incoming_taskid = ProxySniffer._extract_taskid(incoming.url) if incoming.url else None

    if current_has_own_key and incoming_has_own_key:
        # 两个都有 key：优先选有 taskid 的（经过认证的下载链接更可靠）
        if incoming_taskid and not current_taskid:
            preferred_url = incoming.url
            preferred_key = incoming.decryption_key
        else:
            preferred_url = current.url
            preferred_key = current.decryption_key
    elif incoming_has_own_key:
        # 只有 incoming 有 key：用 incoming 的 URL+key 配对
        preferred_url = incoming.url
        preferred_key = incoming.decryption_key
    elif current_has_own_key:
        # 只有 current 有 key：保持 current 的 URL+key 配对
        preferred_url = current.url
        preferred_key = current.decryption_key
    else:
        # 都没有 key
        preferred_url = current.url or incoming.url
        preferred_key = current.decryption_key or incoming.decryption_key

    preferred_encryption = current.encryption_type
    if preferred_encryption == EncryptionType.UNKNOWN:
        preferred_encryption = incoming.encryption_type
    if preferred_encryption == EncryptionType.UNKNOWN:
        preferred_encryption = sniffer._infer_encryption_type(preferred_url, preferred_key)

    return DetectedVideo(
        id=current.id or incoming.id,
        url=preferred_url,
        title=preferred_title,
        duration=current.duration if current.duration is not None else incoming.duration,
        resolution=current.resolution or incoming.resolution,
        filesize=current.filesize if current.filesize is not None else incoming.filesize,
        thumbnail=current.thumbnail or incoming.thumbnail,
        detected_at=max(current.detected_at, incoming.detected_at),
        encryption_type=preferred_encryption,
        decryption_key=preferred_key,
    )


def _prepare_display_videos(sniffer: ProxySniffer, videos: List[Any]) -> List[DetectedVideo]:
    merged: Dict[str, DetectedVideo] = {}
    ordered_keys: List[str] = []
    # 多维度去重映射：video.id / taskid / title → merge_key
    seen_ids: Dict[str, str] = {}

    def _find_existing_key(normalized: DetectedVideo) -> Optional[str]:
        """按 video.id、taskid、稳定标题查找已存在的 merge_key。"""
        # 按 video.id
        vid = normalized.id
        if vid and vid in seen_ids:
            key = seen_ids[vid]
            if key in merged:
                return key
        # 按 taskid（同一视频不同画质共享 taskid）
        taskid = ProxySniffer._extract_taskid(normalized.url)
        if taskid:
            taskid_key = f"taskid:{taskid}"
            if taskid_key in seen_ids:
                key = seen_ids[taskid_key]
                if key in merged:
                    return key
        # 按稳定标题（同一视频从不同检测路径进入，一个有 taskid 一个没有）
        title = _normalize_identity_text(normalized.title)
        if title and not _is_fallback_channels_title(normalized.title):
            title_key = f"title:{title}"
            if title_key in seen_ids:
                key = seen_ids[title_key]
                if key in merged:
                    return key
        return None

    def _register_keys(normalized: DetectedVideo, merge_key: str) -> None:
        """注册所有去重键。"""
        vid = normalized.id
        if vid:
            seen_ids[vid] = merge_key
        taskid = ProxySniffer._extract_taskid(normalized.url)
        if taskid:
            seen_ids[f"taskid:{taskid}"] = merge_key
        title = _normalize_identity_text(normalized.title)
        if title and not _is_fallback_channels_title(normalized.title):
            seen_ids[f"title:{title}"] = merge_key

    for video in videos:
        normalized = _normalize_detected_video_for_display(sniffer, video)
        if not normalized:
            continue

        merge_key = _build_channels_item_identity(
            url=normalized.url,
            title=normalized.title,
            duration=normalized.duration,
            resolution=normalized.resolution,
            filesize=normalized.filesize,
            thumbnail=normalized.thumbnail,
            decryption_key=normalized.decryption_key,
        )

        # 优先按 video.id / taskid / title 去重
        existing_key = _find_existing_key(normalized)
        if existing_key:
            merged[existing_key] = _merge_display_videos(sniffer, merged[existing_key], normalized)
            _register_keys(normalized, existing_key)
            continue

        if merge_key in merged:
            merged[merge_key] = _merge_display_videos(sniffer, merged[merge_key], normalized)
            _register_keys(normalized, merge_key)
            continue

        merged[merge_key] = normalized
        ordered_keys.append(merge_key)
        _register_keys(normalized, merge_key)

    result = [merged[key] for key in ordered_keys]

    # 过滤掉完全无用的 placeholder 条目：同时缺少 decodeKey、标题、缩略图
    # 这些条目通常是在代理启动前已存在的视频流，对用户没有任何价值
    result = [
        v for v in result
        if not (
            len(_collect_video_placeholder_reasons(v)) >= 3
        )
    ]

    return result


def _build_video_payload(video: Any) -> Dict[str, Any]:
    """Build API payload for a detected video with placeholder hints."""
    data = video.to_dict()
    placeholder_reasons = _collect_video_placeholder_reasons(video)
    placeholder_messages: List[str] = []
    if "missing_decode_key" in placeholder_reasons:
        placeholder_messages.append("未捕获到 decodeKey，请在启动嗅探后重新打开视频号页面并完整播放一遍。")
    if "missing_title" in placeholder_reasons or "missing_thumbnail" in placeholder_reasons:
        placeholder_messages.append("当前只抓到了原始视频地址，标题和缩略图等页面元数据尚未获取。")

    if placeholder_messages:
        data["is_placeholder"] = True
        data["placeholder_message"] = " ".join(placeholder_messages)

    return data


def _merge_download_task_payload(current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge duplicate download tasks while preserving the newest task state."""
    merged = dict(current)
    merged["title"] = _pick_preferred_task_title(current.get("title"), incoming.get("title"))
    merged["thumbnail"] = current.get("thumbnail") or incoming.get("thumbnail")
    merged["file_path"] = current.get("file_path") or incoming.get("file_path")
    merged["error"] = current.get("error") or incoming.get("error")
    merged["total"] = max(int(current.get("total") or 0), int(incoming.get("total") or 0))
    merged["downloaded"] = max(int(current.get("downloaded") or 0), int(incoming.get("downloaded") or 0))
    merged["speed"] = float(current.get("speed") or incoming.get("speed") or 0)
    return merged


def _prepare_download_task_payloads(tasks: List[DownloadTask]) -> List[Dict[str, Any]]:
    """Deduplicate visually identical channel download tasks for list display."""
    merged: Dict[str, Dict[str, Any]] = {}
    ordered_keys: List[str] = []

    for task in tasks:
        payload = _task_to_channels_payload(task)
        merge_key = _build_channels_item_identity(
            url=payload.get("url"),
            title=payload.get("title"),
            duration=getattr(task, "duration", None),
            resolution=None,
            filesize=getattr(task, "filesize", None),
            thumbnail=payload.get("thumbnail"),
            decryption_key=None,
        )
        if merge_key in merged:
            merged[merge_key] = _merge_download_task_payload(merged[merge_key], payload)
            continue

        merged[merge_key] = payload
        ordered_keys.append(merge_key)

    return [merged[key] for key in ordered_keys]


def _resolve_download_output_path(
    url: str,
    title: Optional[str],
    preferred_path: Optional[str],
) -> Optional[str]:
    """Resolve an explicit output file path for channels downloads."""
    raw_path = str(preferred_path or "").strip()
    if not raw_path:
        return None

    candidate = Path(raw_path).expanduser()
    file_suffixes = {
        ".mp4",
        ".m4v",
        ".mov",
        ".mkv",
        ".webm",
        ".avi",
        ".flv",
        ".ts",
        ".tmp",
        ".encrypted",
    }

    if candidate.exists() and candidate.is_dir():
        filename = f"{ChannelsDownloader._select_output_stem(url, title)}.mp4"
        return str(candidate / filename)

    if candidate.suffix.lower() in file_suffixes:
        return str(candidate)

    filename = f"{ChannelsDownloader._select_output_stem(url, title)}.mp4"
    return str(candidate / filename)


async def _update_download_task(task_id: str, **updates: Any) -> Optional[DownloadTask]:
    """更新下载任务并提交。"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(DownloadTask).where(DownloadTask.task_id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return None

        for key, value in updates.items():
            setattr(task, key, value)

        await session.commit()
        return task


def _attach_download_task_callback(task_id: str) -> None:
    """注册后台下载任务完成回调。"""
    def _on_done(task: asyncio.Task[Any]) -> None:
        _download_tasks.pop(task_id, None)
        try:
            task.result()
        except asyncio.CancelledError:
            logger.info("Channels download task cancelled: %s", task_id)
        except Exception:
            logger.exception("Channels download task failed: %s", task_id)

    background_task = _download_tasks.get(task_id)
    if background_task:
        background_task.add_done_callback(_on_done)


async def _run_download_task(
    task_id: str,
    *,
    url: str,
    quality: str,
    output_path: Optional[str],
    auto_decrypt: bool,
    decryption_key: Optional[str],
    title: Optional[str],
) -> None:
    """后台执行视频号下载任务并落库状态。"""
    await _update_download_task(
        task_id,
        status="downloading",
        started_at=datetime.utcnow(),
        progress=0.0,
        error_message=None,
    )

    last_progress_update = 0.0

    async def progress_callback(progress_data: Dict[str, Any]) -> None:
        nonlocal last_progress_update

        now = time.monotonic()
        status = progress_data.get("status", "downloading")
        progress = float(progress_data.get("progress", 0) or 0)
        downloaded = int(progress_data.get("downloaded", progress_data.get("downloaded_bytes", 0)) or 0)
        total = int(progress_data.get("total", progress_data.get("total_bytes", 0)) or 0)
        speed = float(progress_data.get("speed", 0) or 0)
        eta = int(progress_data.get("eta", 0) or 0)

        target_status = "decrypting" if status == "decrypting" else "downloading"
        should_commit = (
            target_status == "decrypting"
            or now - last_progress_update >= 0.6
            or progress >= 100
        )
        if not should_commit:
            return

        await _update_download_task(
            task_id,
            status=target_status,
            progress=max(0.0, min(100.0, progress)),
            downloaded_bytes=max(0, downloaded),
            total_bytes=max(0, total),
            speed=max(0.0, speed),
            eta=max(0, eta),
        )
        last_progress_update = now

    try:
        downloader = get_downloader()
        result = await downloader.download_video(
            url=url,
            quality=quality,
            output_path=output_path,
            task_id=task_id,
            progress_callback=progress_callback,
            auto_decrypt=auto_decrypt,
            decryption_key=decryption_key,
            title=title,
        )

        if result.get("success"):
            file_path = result.get("file_path")
            file_size = int(result.get("file_size") or 0)
            is_encrypted_payload = bool(result.get("encrypted") and not result.get("decrypted"))
            task_error = result.get("decrypt_hint") if is_encrypted_payload else None
            final_status = "encrypted" if is_encrypted_payload else "completed"
            await _update_download_task(
                task_id,
                status=final_status,
                progress=100.0,
                completed_at=datetime.utcnow(),
                filename=file_path if file_path else None,
                filesize=file_size,
                error_message=task_error,
            )
            logger.info(
                "Channels download task resolved: task=%s status=%s autoDecrypt=%s decodeKey=%s encryptedPayload=%s decrypted=%s file=%s size=%s hint=%s url=%s",
                task_id,
                final_status,
                "yes" if auto_decrypt else "no",
                "yes" if _normalize_decode_key(decryption_key) else "no",
                "yes" if bool(result.get("encrypted")) else "no",
                "yes" if bool(result.get("decrypted")) else "no",
                _preview_log_value(file_path, 144),
                file_size,
                _preview_log_value(task_error, 96),
                _preview_log_value(url, 144),
            )
            return

        error_message = result.get("error") or "下载失败"
        error_code = str(result.get("error_code") or "")
        is_cancelled = error_code.upper() == "DOWNLOAD_CANCELLED"
        final_status = "cancelled" if is_cancelled else "failed"
        await _update_download_task(
            task_id,
            status=final_status,
            completed_at=datetime.utcnow(),
            error_message="用户取消下载" if is_cancelled else error_message,
        )
        logger.info(
            "Channels download task resolved: task=%s status=%s autoDecrypt=%s decodeKey=%s errorCode=%s error=%s url=%s",
            task_id,
            final_status,
            "yes" if auto_decrypt else "no",
            "yes" if _normalize_decode_key(decryption_key) else "no",
            _preview_log_value(error_code, 48),
            _preview_log_value("用户取消下载" if is_cancelled else error_message, 96),
            _preview_log_value(url, 144),
        )
    except asyncio.CancelledError:
        try:
            get_downloader().cancel_download(task_id)
        except Exception:
            logger.debug("cancel_download failed for %s", task_id, exc_info=True)
        await _update_download_task(
            task_id,
            status="cancelled",
            completed_at=datetime.utcnow(),
            error_message="用户取消下载",
        )
        logger.info(
            "Channels download task resolved: task=%s status=cancelled autoDecrypt=%s decodeKey=%s url=%s",
            task_id,
            "yes" if auto_decrypt else "no",
            "yes" if _normalize_decode_key(decryption_key) else "no",
            _preview_log_value(url, 144),
        )
        raise
    except Exception as exc:
        logger.exception("Unexpected channels download error for task %s", task_id)
        await _update_download_task(
            task_id,
            status="failed",
            completed_at=datetime.utcnow(),
            error_message=str(exc),
        )
        logger.info(
            "Channels download task resolved: task=%s status=failed autoDecrypt=%s decodeKey=%s error=%s url=%s",
            task_id,
            "yes" if auto_decrypt else "no",
            "yes" if _normalize_decode_key(decryption_key) else "no",
            _preview_log_value(exc, 96),
            _preview_log_value(url, 144),
        )


def _normalize_capture_mode(value: Optional[str]) -> CaptureMode:
    """规范化捕获模式。"""
    if not value:
        return _capture_config.capture_mode
    try:
        mode = CaptureMode(value)
    except ValueError:
        logger.warning("Unknown capture mode %r, fallback to proxy_only", value)
        mode = CaptureMode.PROXY_ONLY

    if mode not in (CaptureMode.PROXY_ONLY, CaptureMode.TRANSPARENT):
        logger.info("Capture mode %s is not supported by legacy channels API, fallback to proxy_only", mode.value)
        return CaptureMode.PROXY_ONLY

    return mode


def _resolve_target_processes(target_processes: Optional[List[str]]) -> List[str]:
    """Resolve transparent capture targets and upgrade legacy defaults."""
    normalized = [str(name).strip() for name in (target_processes or []) if str(name).strip()]
    if not normalized:
        return resolve_local_capture_processes()

    unique: List[str] = []
    seen = set()
    for name in normalized:
        lowered = name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(name)

    unique_set = {name.lower() for name in unique}
    legacy_default_targets = {name.lower() for name in _LEGACY_DEFAULT_TARGET_PROCESSES}
    if unique_set == _PREVIOUS_DEFAULT_TARGET_PROCESSES:
        return resolve_local_capture_processes()

    if unique_set.issubset(legacy_default_targets) or (
        unique_set
        and unique_set.isdisjoint(_HELPER_PROCESS_NAME_SET)
        and unique_set.issubset(_DEFAULT_WECHAT_CORE_PROCESS_SET)
    ):
        logger.debug(
            "Expanded legacy target process list %s to full WeChat process set",
            unique,
        )
        return resolve_local_capture_processes()

    return resolve_local_capture_processes(unique)


_capture_config.target_processes = _resolve_target_processes(_capture_config.target_processes)


def _is_transparent_mode(mode: CaptureMode) -> bool:
    """当前模式是否需要透明捕获。"""
    return mode == CaptureMode.TRANSPARENT


def _get_default_proxy_port() -> int:
    """获取当前默认代理端口。"""
    try:
        return int(_runtime_config.get("proxy_port", 8888))
    except (TypeError, ValueError):
        return 8888


def _is_port_available(port: int) -> bool:
    """检查端口是否可用。"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _pick_available_proxy_port(preferred_port: int) -> int:
    """优先使用指定端口，冲突时回退到系统分配的可用端口。"""
    if _is_port_available(preferred_port):
        return preferred_port

    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    logger.warning("Preferred proxy port %s is in use, fallback to port %s", preferred_port, port)
    return port


def get_driver_manager() -> DriverManager:
    """获取驱动管理器实例。"""
    global _driver_manager
    if _driver_manager is None:
        _driver_manager = DriverManager()
    return _driver_manager


def get_proxy_detector() -> ProxyDetector:
    """获取代理环境探测器实例。"""
    global _proxy_detector
    if _proxy_detector is None:
        _proxy_detector = ProxyDetector()
    return _proxy_detector


async def _detect_proxy_info() -> ProxyInfo:
    """探测当前代理环境。"""
    try:
        return await get_proxy_detector().detect()
    except Exception:
        logger.exception("Failed to detect proxy environment")
        return ProxyInfo()


def _build_proxy_environment_warning(proxy_info: Optional[ProxyInfo]) -> Optional[str]:
    """为当前代理环境生成对视频号抓取有意义的告警。"""
    if not proxy_info or getattr(proxy_info, "proxy_type", None) is None:
        return None

    if str(proxy_info.proxy_type.value) == "none":
        return None

    process_name = proxy_info.process_name or "该代理"

    if proxy_info.is_tun_enabled or proxy_info.proxy_mode == ProxyMode.TUN:
        return (
            f"检测到代理 {process_name} 正在使用 TUN 模式，这会拦截微信页面元数据流量，"
            "当前很可能只能抓到原始视频地址。请退出该代理，或将 Weixin.exe、WeChatAppEx.exe、"
            f"{_HELPER_PROCESS_HINT}、channels.weixin.qq.com、finder.video.qq.com 设为直连。"
        )

    if proxy_info.proxy_mode == ProxyMode.SYSTEM_PROXY:
        return (
            f"检测到代理 {process_name} 正在通过系统代理/PAC 接管流量，这会让微信辅助浏览器进程继续走本地代理，"
            "从而导致视频号页面元数据抓取不完整。请将 Weixin.exe、WeChatAppEx.exe、"
            f"{_HELPER_PROCESS_HINT}、channels.weixin.qq.com、finder.video.qq.com 设为直连，"
            "或在透明抓取前暂时关闭系统代理/PAC。"
        )

    if proxy_info.proxy_mode == ProxyMode.FAKE_IP or proxy_info.is_fake_ip_enabled:
        return (
            f"检测到代理 {process_name} 启用了 Fake-IP，这可能导致视频号元数据抓取不完整。"
            f"建议将 Weixin.exe、WeChatAppEx.exe、{_HELPER_PROCESS_HINT}、"
            "channels.weixin.qq.com、finder.video.qq.com 设为直连。"
        )

    return (
        f"检测到代理 {process_name} 正在运行。若视频号列表里只出现原始 stodownload 链接，"
        f"请将 Weixin.exe、WeChatAppEx.exe、{_HELPER_PROCESS_HINT}、"
        "channels.weixin.qq.com、finder.video.qq.com 设为直连。"
    )


def _build_transparent_start_blocker(proxy_info: Optional[ProxyInfo]) -> Optional[Dict[str, str]]:
    """Return a blocking error when transparent capture would conflict with TUN routing."""
    if not proxy_info or getattr(proxy_info, "proxy_type", None) is None:
        return None

    if str(proxy_info.proxy_type.value) == "none":
        return None

    process_name = proxy_info.process_name or "该代理"
    if proxy_info.is_tun_enabled or proxy_info.proxy_mode == ProxyMode.TUN:
        return {
            "error_code": "PROXY_TUN_MODE",
            "error_message": (
                f"检测到代理 {process_name} 正在使用 TUN 模式，透明嗅探会与 WinDivert 冲突。"
                "请先关闭 TUN，或将 Weixin.exe、WeChatAppEx.exe、"
                f"{_HELPER_PROCESS_HINT}、channels.weixin.qq.com、finder.video.qq.com 设为直连后，再启动嗅探。"
            ),
        }

    return None


def _build_channels_certificate_warning(cert_info: Optional[Dict[str, Any]]) -> Optional[str]:
    """Explain the most likely metadata failure when WeChat-compatible cert import is incomplete."""
    if not cert_info:
        return None

    if not cert_info.get("cert_installed"):
        return (
            "当前未安装 mitmproxy 根证书。微信 4.x 页面元数据通常无法解密，"
            "只会抓到 stodownload 原始地址。请先安装系统 CER，再导入微信兼容 P12，"
            "然后完全重启微信。"
        )

    if cert_info.get("cert_p12_exists") and not cert_info.get("wechat_p12_installed"):
        if cert_info.get("wechat_p12_subject_present"):
            return (
                "当前用户证书库里虽然已经存在 mitmproxy 证书，但没有检测到私钥。"
                "这通常是只导入了 mitmproxy-ca-cert.p12，未导入带私钥的 mitmproxy-ca.p12。"
                "这种情况下微信 4.x 常见表现就是只有 stodownload，没有标题、缩略图和 decodeKey。"
                "请重新导入微信兼容 P12 后完全重启微信。"
            )
        return (
            "已检测到系统根证书，但当前用户证书库里还没有导入微信兼容 P12。"
            "这类情况下微信 4.x 常见表现就是只有 stodownload，没有标题、缩略图和 decodeKey。"
            "请在证书管理里导入 P12 后完全重启微信。"
        )

    return None


def get_cert_installer():
    """按需获取 mitmproxy 证书安装器。"""
    global _cert_installer, _cert_manager
    if _cert_installer is None:
        from ..utils.cert_installer import CertInstaller

        _cert_installer = CertInstaller()
    if _cert_manager is None:
        _cert_manager = _cert_installer
    return _cert_installer


def get_cert_manager():
    """兼容旧测试和旧调用方的证书管理器访问入口。"""
    return get_cert_installer()


def get_system_proxy_manager():
    """按需获取系统代理管理器，仅 Windows 可用。"""
    global _system_proxy_manager
    if sys.platform != "win32":
        return None
    if _system_proxy_manager is None:
        from ..utils.system_proxy import SystemProxyManager

        _system_proxy_manager = SystemProxyManager()
    return _system_proxy_manager


def _restore_managed_system_proxy() -> bool:
    """Restore system proxy settings previously changed by VidFlow."""
    global _system_proxy_enabled

    proxy_manager = get_system_proxy_manager()
    if proxy_manager is None:
        return True

    if _system_proxy_enabled:
        if proxy_manager.restore_proxy():
            _system_proxy_enabled = False
            return True
        return False

    if proxy_manager.has_persisted_state():
        if proxy_manager.is_current_settings_managed():
            if proxy_manager.restore_proxy():
                _system_proxy_enabled = False
                return True
            return False
        proxy_manager.discard_persisted_state()

    proxy_manager.cleanup_stale_managed_proxy()
    return True


def get_sniffer(
    port: Optional[int] = None,
    capture_mode: Optional[CaptureMode] = None,
) -> ProxySniffer:
    """获取嗅探器实例，并在配置变化时重建。"""
    global _sniffer

    mode = capture_mode or _capture_config.capture_mode
    resolved_port = port or _active_proxy_port or _get_default_proxy_port()
    transparent_mode = _is_transparent_mode(mode)
    resolved_target_processes = _resolve_target_processes(_capture_config.target_processes)
    _capture_config.target_processes = resolved_target_processes

    if (
        _sniffer is None
        or _sniffer.port != resolved_port
        or _sniffer.transparent_mode != transparent_mode
    ):
        # 端口或模式变化时，先尽力停止旧实例释放端口
        if _sniffer is not None and getattr(_sniffer, "is_running", False):
            logger.info(
                "Stopping stale sniffer on port %s before rebuilding on port %s",
                _sniffer.port,
                resolved_port,
            )
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 在已运行的事件循环中无法同步等待，创建后台任务
                    asyncio.ensure_future(_sniffer.stop())
                else:
                    loop.run_until_complete(_sniffer.stop())
            except Exception:
                logger.warning("Failed to stop stale sniffer gracefully", exc_info=True)
        _sniffer = ProxySniffer(
            port=resolved_port,
            transparent_mode=transparent_mode,
            quic_blocking_enabled=_capture_config.quic_blocking_enabled,
            target_processes=resolved_target_processes,
        )
    else:
        _sniffer.quic_blocking_enabled = _capture_config.quic_blocking_enabled
        _sniffer.set_target_processes(resolved_target_processes)
    return _sniffer


def get_sniffer_sync() -> ProxySniffer:
    """兼容旧测试的同步访问入口。"""
    return get_sniffer()


def _build_capture_statistics(sniffer: ProxySniffer) -> dict:
    """构造前端所需的捕获统计结构。"""
    videos = _prepare_display_videos(sniffer, sniffer.get_detected_videos())
    runtime = sniffer.get_runtime_statistics()
    last_detection = None
    if videos:
        last_detection = max(video.detected_at for video in videos).isoformat()

    unrecognized_domains = [
        f"{host} ({count})"
        for host, count in runtime.get("top_hosts", [])
    ]
    placeholder_count = sum(
        1
        for video in videos
        if (
            _is_fallback_channels_title(video.title)
            or not video.thumbnail
            or (_requires_decode_key(video.url, video) and not _normalize_decode_key(video.decryption_key))
        )
    )
    if runtime.get("mmtls_request_count", 0) > 0 and not videos:
        unrecognized_domains.insert(0, f"mmtls_traffic_detected ({runtime['mmtls_request_count']})")
    elif runtime.get("mmtls_request_count", 0) > 0 and placeholder_count:
        unrecognized_domains.insert(0, f"metadata_capture_missing ({placeholder_count})")

    return {
        "packets_intercepted": runtime.get("request_count", 0),
        "connections_redirected": runtime.get("flow_count", 0),
        "videos_detected": len(videos),
        "last_detection_at": last_detection,
        "unrecognized_domains": unrecognized_domains,
        "channels_page_injection_kind": runtime.get("channels_page_injection_kind"),
        "channels_page_injection_url": runtime.get("channels_page_injection_url"),
        "channels_page_injection_at": runtime.get("channels_page_injection_at"),
        "renderer_recycle_attempted": runtime.get("renderer_recycle_attempted", False),
        "renderer_recycle_completed": runtime.get("renderer_recycle_completed", False),
        "renderer_recycle_reason": runtime.get("renderer_recycle_reason"),
        "renderer_recycle_at": runtime.get("renderer_recycle_at"),
    }


def _build_status_payload(sniffer: ProxySniffer) -> dict:
    """构造与前端契约一致的状态响应。"""
    status = sniffer.get_status()
    return {
        "state": status.state.value,
        "proxy_address": status.proxy_address,
        "proxy_port": status.proxy_port,
        "videos_detected": status.videos_detected,
        "started_at": status.started_at.isoformat() if status.started_at else None,
        "error_message": status.error_message,
        "capture_mode": _capture_config.capture_mode.value,
        "capture_state": status.state.value,
        "capture_started_at": status.started_at.isoformat() if status.started_at else None,
        "statistics": _build_capture_statistics(sniffer),
    }


def get_downloader() -> ChannelsDownloader:
    """获取下载器实例"""
    global _downloader
    if _downloader is None:
        download_dir = get_data_dir() / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        _downloader = ChannelsDownloader(output_dir=str(download_dir), auto_decrypt=True)
    return _downloader


# ==================== 数据模型 ====================

class SnifferStartResponse(BaseModel):
    """Backward-compatible start response model used by tests and typed callers."""

    success: bool
    proxy_address: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    capture_mode: Optional[str] = None
    requires_admin: Optional[bool] = None
    requires_driver: Optional[bool] = None
    requires_certificate: Optional[bool] = None
    certificate_warning: Optional[str] = None


class SnifferStatusResponse(BaseModel):
    """Typed sniffer status payload."""

    state: str = "stopped"
    proxy_address: Optional[str] = None
    proxy_port: int = 8888
    videos_detected: int = 0
    started_at: Optional[str] = None
    error_message: Optional[str] = None
    capture_mode: Optional[str] = None
    capture_state: Optional[str] = None
    capture_started_at: Optional[str] = None
    statistics: Optional[Dict[str, Any]] = None


class DetectedVideoResponse(BaseModel):
    """Typed detected video payload."""

    id: str
    url: str
    title: Optional[str] = None
    duration: Optional[int] = None
    detected_at: Optional[str] = None
    encryption_type: Optional[str] = None
    thumbnail: Optional[str] = None
    decryption_key: Optional[str] = None
    placeholder_message: Optional[str] = None
    is_placeholder: Optional[bool] = None


class DownloadResponse(BaseModel):
    """Typed download response payload."""

    success: bool
    task_id: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    status: Optional[str] = None
    message: Optional[str] = None
    error_message: Optional[str] = None


class CertInfoResponse(BaseModel):
    """Typed certificate info payload."""

    exists: bool
    valid: bool
    expires_at: Optional[str] = None
    fingerprint: Optional[str] = None
    path: Optional[str] = None
    root_installed: Optional[bool] = None
    wechat_p12_path: Optional[str] = None
    wechat_p12_exists: Optional[bool] = None
    wechat_p12_installed: Optional[bool] = None
    wechat_p12_subject_present: Optional[bool] = None
    wechat_p12_sources: Optional[List[str]] = None
    recommended_format: Optional[str] = None


class ConfigResponse(BaseModel):
    """Typed runtime config payload."""

    proxy_port: int = 8888
    download_dir: str = ""
    auto_decrypt: bool = True
    auto_clean_wechat_cache: bool = True
    quality_preference: str = "best"
    clear_on_exit: bool = False


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


class InjectedVideoPayload(BaseModel):
    """Metadata payload posted by the in-page Channels injection script."""
    url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    decodeKey: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    videoWidth: Optional[int] = None
    videoHeight: Optional[int] = None
    fileSize: Optional[int] = None
    cacheKeys: Optional[List[str]] = None
    pageUrl: Optional[str] = None
    source: Optional[str] = None


class DownloadRequest(BaseModel):
    """下载请求"""
    url: str
    quality: Optional[str] = None
    output_path: Optional[str] = None
    auto_decrypt: Optional[bool] = None
    decryption_key: Optional[str] = None


class CancelDownloadRequest(BaseModel):
    """取消下载请求。"""
    task_id: str


class SnifferStartRequest(BaseModel):
    """启动嗅探器请求。"""
    port: Optional[int] = None
    capture_mode: Optional[str] = None


class CertificateExportRequest(BaseModel):
    """证书导出请求。"""
    export_path: str
    format: Optional[str] = "cer"


class QUICToggleRequest(BaseModel):
    """QUIC 阻止开关请求。"""
    enabled: bool


class ConfigUpdate(BaseModel):
    """配置更新"""
    proxy_port: Optional[int] = None
    download_dir: Optional[str] = None
    auto_decrypt: Optional[bool] = None
    auto_clean_wechat_cache: Optional[bool] = None
    quality_preference: Optional[str] = None
    clear_on_exit: Optional[bool] = None


class ConfigUpdateRequest(ConfigUpdate):
    """Backward-compatible alias for the runtime config update payload."""


# ==================== 嗅探器 API ====================

@router.get("/sniffer/status")
async def get_sniffer_status():
    """获取嗅探器状态"""
    try:
        sniffer = get_sniffer()
        return _build_status_payload(sniffer)
    except Exception as e:
        logger.error(f"Error getting sniffer status: {e}")
        raise HTTPException(status_code=500, detail=f"获取嗅探器状态失败: {str(e)}")


@router.post("/sniffer/start")
async def start_sniffer(request: SnifferStartRequest):
    """启动嗅探器"""
    global _active_proxy_port, _system_proxy_enabled

    try:
        cache_cleanup_result: Optional[Dict[str, Any]] = None
        proxy_info = await _detect_proxy_info()
        proxy_warning = _build_proxy_environment_warning(proxy_info)
        cert_info = await asyncio.to_thread(get_cert_installer().get_cert_info)
        capture_mode = _normalize_capture_mode(request.capture_mode)
        _capture_config.capture_mode = capture_mode
        _capture_config.use_windivert = _is_transparent_mode(capture_mode)
        proxy_manager = get_system_proxy_manager()
        disabled_system_proxy_for_transparent = False
        fallback_warning: Optional[str] = None

        if not await asyncio.to_thread(_restore_managed_system_proxy):
            return {
                "success": False,
                "proxy_address": None,
                "error_message": "恢复之前由 VidFlow 接管的系统代理设置失败，请先手动关闭系统代理/PAC 后再试。",
                "error_code": "SYSTEM_PROXY_RESTORE_FAILED",
                "capture_mode": capture_mode.value,
            }

        if _is_transparent_mode(capture_mode):
            start_blocker = _build_transparent_start_blocker(proxy_info)
            if start_blocker:
                # 自动回退到显式代理模式，而非阻止启动
                logger.warning(
                    "Transparent mode blocked (%s), auto-fallback to explicit proxy mode",
                    start_blocker["error_code"],
                )
                capture_mode = CaptureMode.PROXY_ONLY
                _capture_config.capture_mode = capture_mode
                _capture_config.use_windivert = False
                fallback_warning = (
                    f"⚠ {start_blocker['error_message']} "
                    "已自动切换为显式代理模式。显式代理模式下，HTTP/2 连接复用可能导致后续视频无法捕获，"
                    "建议每次切换视频后重新打开视频号页面。"
                )

        preferred_port = request.port or _get_default_proxy_port()
        selected_port = preferred_port if request.port else _pick_available_proxy_port(preferred_port)
        sniffer = get_sniffer(port=selected_port, capture_mode=capture_mode)

        if _is_transparent_mode(capture_mode):
            driver_status = await asyncio.to_thread(get_driver_manager().get_status)
            if not driver_status.is_admin:
                logger.warning("Transparent mode requested without admin privileges")
                return {
                    "success": False,
                    "proxy_address": None,
                    "error_message": "需要管理员权限才能使用透明捕获模式。请以管理员身份重新启动应用。",
                    "error_code": "ADMIN_REQUIRED",
                    "capture_mode": capture_mode.value,
                    "requires_admin": True,
                }

            if driver_status.state != DriverState.INSTALLED:
                logger.warning("Transparent mode requested without WinDivert driver installed")
                return {
                    "success": False,
                    "proxy_address": None,
                    "error_message": driver_status.error_message or "WinDivert 驱动未安装",
                    "error_code": "DRIVER_MISSING",
                    "capture_mode": capture_mode.value,
                    "requires_driver": True,
                }
        else:
            if not cert_info.get("cert_installed"):
                logger.warning("Proxy mode requested without mitmproxy certificate installed")
                return {
                    "success": False,
                    "proxy_address": None,
                    "error_message": "代理模式需要先安装 mitmproxy 证书。",
                    "error_code": "CERT_MISSING",
                    "capture_mode": capture_mode.value,
                    "requires_certificate": True,
                }

        if _is_transparent_mode(capture_mode) and proxy_manager and await asyncio.to_thread(proxy_manager.has_active_proxy):
            if not await asyncio.to_thread(proxy_manager.disable_proxy):
                return {
                    "success": False,
                    "proxy_address": None,
                    "error_message": "透明捕获模式启动前无法临时关闭系统代理/PAC。请先关闭 Clash PAC/系统代理后再试。",
                    "error_code": "SYSTEM_PROXY_DISABLE_FAILED",
                    "capture_mode": capture_mode.value,
                }
            _system_proxy_enabled = True
            disabled_system_proxy_for_transparent = True

        result = await sniffer.start()
        payload = result.to_dict()
        payload["capture_mode"] = capture_mode.value
        payload["proxy_info"] = proxy_info.to_dict()
        _active_proxy_port = sniffer.port if payload.get("success") else None

        if payload.get("success"):
            sniffer.clear_videos()

        if not payload.get("success") and disabled_system_proxy_for_transparent:
            await asyncio.to_thread(_restore_managed_system_proxy)

        if payload.get("success") and capture_mode == CaptureMode.PROXY_ONLY:
            if proxy_manager and not _system_proxy_enabled:
                proxy_address = f"127.0.0.1:{sniffer.port}"
                if await asyncio.to_thread(proxy_manager.set_proxy, proxy_address):
                    _system_proxy_enabled = True
                    payload["system_proxy"] = proxy_address
                else:
                    await sniffer.stop()
                    _active_proxy_port = None
                    payload.update({
                        "success": False,
                        "proxy_address": None,
                        "error_message": "系统代理设置失败，无法将微信流量导入嗅探器。",
                        "error_code": "PERMISSION_DENIED",
                    })

        if payload.get("success") and capture_mode == CaptureMode.PROXY_ONLY:
            cache_cleanup_result = await asyncio.to_thread(_auto_prepare_wechat_channels_cache, sniffer)
            if not cache_cleanup_result.get("message"):
                sniffer.proactively_recycle_wechat_renderer_on_startup()

        if payload.get("success"):
            warnings: List[str] = []
            if cache_cleanup_result:
                payload["cache_cleanup"] = cache_cleanup_result
                cache_cleanup_message = str(cache_cleanup_result.get("message") or "").strip()
                if cache_cleanup_message:
                    warnings.append(cache_cleanup_message)
            if fallback_warning:
                warnings.append(fallback_warning)
            cert_warning = _build_channels_certificate_warning(cert_info)
            if cert_warning:
                warnings.append(cert_warning)
            if proxy_warning and not (
                disabled_system_proxy_for_transparent
                and not proxy_info.is_tun_enabled
                and not proxy_info.is_fake_ip_enabled
            ):
                warnings.append(proxy_warning)
            if warnings:
                payload["error_message"] = " ".join(_dedupe_messages(warnings))

        return payload
    except Exception as e:
        if _is_transparent_mode(_capture_config.capture_mode):
            _restore_managed_system_proxy()
        logger.error(f"Error starting sniffer: {e}")
        raise HTTPException(status_code=500, detail=f"启动嗅探器失败: {str(e)}")


@router.post("/sniffer/stop")
async def stop_sniffer():
    """停止嗅探器"""
    global _active_proxy_port, _system_proxy_enabled

    try:
        sniffer = get_sniffer()
        success = await sniffer.stop()
        _active_proxy_port = None

        proxy_restored = True
        if _system_proxy_enabled:
            proxy_restored = await asyncio.to_thread(_restore_managed_system_proxy)

        if success and proxy_restored:
            return {"success": True, "message": "嗅探器已停止"}
        if success and not proxy_restored:
            return {"success": False, "message": "嗅探器已停止，但系统代理恢复失败"}
        return {"success": False, "message": "停止失败"}
    except Exception as e:
        logger.error(f"Error stopping sniffer: {e}")
        raise HTTPException(status_code=500, detail=f"停止嗅探器失败: {str(e)}")


async def shutdown_capture_resources() -> None:
    """Best-effort cleanup for app shutdown to avoid stale local proxy settings."""
    global _active_proxy_port

    try:
        sniffer = get_sniffer()
    except Exception:
        sniffer = None

    try:
        if sniffer is not None and getattr(sniffer, "is_running", False):
            await sniffer.stop()
    except Exception:
        logger.exception("Failed to stop sniffer during shutdown cleanup")
    finally:
        _active_proxy_port = None

    try:
        proxy_manager = get_system_proxy_manager()
        if proxy_manager and (_system_proxy_enabled or proxy_manager.has_persisted_state()):
            if not await asyncio.to_thread(_restore_managed_system_proxy):
                logger.warning("Failed to restore managed system proxy during shutdown cleanup")
    except Exception:
        logger.exception("Failed to cleanup managed system proxy during shutdown")


# ==================== 视频管理 API ====================

@router.get("/videos")
async def get_videos():
    """获取检测到的视频列表"""
    try:
        sniffer = get_sniffer()
        videos = _prepare_display_videos(sniffer, sniffer.get_detected_videos())
        _log_display_video_snapshot(videos)
        logger.info(f"返回 {len(videos)} 个视频")
        return [_build_video_payload(video) for video in videos]
    except Exception as e:
        logger.error(f"Error getting videos: {e}")
        raise HTTPException(status_code=500, detail=f"获取视频列表失败: {str(e)}")


@router.delete("/videos")
async def clear_videos():
    """清空视频列表"""
    try:
        global _last_video_list_snapshot
        sniffer = get_sniffer()
        sniffer.clear_videos()
        _last_video_list_snapshot = None
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


@router.get("/inject-script.js")
async def get_inject_script():
    """Serve the Channels metadata injection script."""
    try:
        return Response(
            content=_load_inject_script(),
            media_type="application/javascript; charset=utf-8",
        )
    except Exception as e:
        logger.error(f"Error loading inject script: {e}")
        raise HTTPException(status_code=500, detail=f"加载注入脚本失败: {str(e)}")


@router.post("/videos/inject")
async def inject_video(payload: InjectedVideoPayload):
    """Accept metadata captured by the in-page Channels injection script."""
    try:
        normalized_url = ChannelsDownloader._normalize_video_url((payload.url or "").strip())
        if not normalized_url:
            # 即使没有 URL，如果有 decodeKey 也要暂存（API 包裹可能先拿到 key 再拿到 URL）
            dk = _normalize_decode_key(payload.decodeKey)
            if dk:
                sniffer = get_sniffer()
                from ..core.channels.models import VideoMetadata
                metadata = VideoMetadata(
                    title=payload.title,
                    decode_key=dk,
                    thumbnail=payload.thumbnail,
                )
                cache_keys = []
                if payload.cacheKeys:
                    cache_keys.extend(payload.cacheKeys)
                if sniffer._video_sniffer_addon and cache_keys:
                    sniffer._video_sniffer_addon.cache_external_metadata(metadata, cache_keys)
                # 同时暂存到 pending decode key 缓存
                sniffer._pending_decode_keys = getattr(sniffer, '_pending_decode_keys', {})
                sniffer._pending_decode_keys[dk] = {
                    "title": payload.title,
                    "thumbnail": payload.thumbnail,
                    "source": payload.source,
                }
                logger.info(
                    "暂存 decodeKey（无 URL）: dk=%s title=%s source=%s",
                    dk[:10] + "..." if len(dk) > 10 else dk,
                    payload.title,
                    payload.source,
                )
                return {"success": True, "cached_decode_key": True}
            raise HTTPException(status_code=400, detail="缺少有效视频 URL")

        sniffer = get_sniffer()
        video = sniffer.ingest_injected_video(
            url=normalized_url,
            title=payload.title,
            thumbnail=payload.thumbnail,
            duration=payload.duration,
            width=payload.videoWidth,
            height=payload.videoHeight,
            filesize=payload.fileSize,
            decode_key=_normalize_decode_key(payload.decodeKey),
            page_url=payload.pageUrl,
            extra_cache_keys=payload.cacheKeys,
        )

        if video is None:
            raise HTTPException(status_code=500, detail="注入元数据处理失败")

        async with AsyncSessionLocal() as session:
            stmt = (
                select(DownloadTask)
                .where(DownloadTask.url == normalized_url)
                .where(
                    or_(
                        DownloadTask.platform.in_(_CHANNEL_TASK_PLATFORMS),
                        DownloadTask.task_id.like("channels_%"),
                    )
                )
            )
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            for task in tasks:
                if video.title:
                    task.title = video.title
                if video.thumbnail:
                    task.thumbnail = video.thumbnail
            if tasks:
                await session.commit()

        logger.info(
            "Injected channels metadata accepted: title=%s thumb=%s decodeKey=%s",
            video.title,
            "yes" if video.thumbnail else "no",
            "yes" if video.decryption_key else "no",
        )
        return {"success": True, "video": video.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error injecting video metadata: {e}")
        raise HTTPException(status_code=500, detail=f"注入视频元数据失败: {str(e)}")



@router.get("/proxy/image")
async def proxy_channels_image(url: str = Query(..., min_length=1)):
    """Backward-compatible image proxy endpoint for channels thumbnails."""
    return await shared_proxy_image(url)


# ==================== 下载管理 API ====================

@router.post("/download")
async def download_video(request: DownloadRequest):
    """下载视频"""
    try:
        if not request.url or not request.url.strip():
            raise HTTPException(status_code=400, detail="下载链接不能为空")

        normalized_url = ChannelsDownloader._normalize_video_url(request.url.strip())
        detected_video = _resolve_detected_video(normalized_url)
        requested_decode_key = _normalize_decode_key(request.decryption_key)
        detected_decode_key = _normalize_decode_key(
            detected_video.decryption_key if detected_video else None
        )
        decode_key = requested_decode_key or detected_decode_key
        requires_decode_key = _requires_decode_key(normalized_url, detected_video)
        if requires_decode_key and not decode_key:
            logger.info(
                "Proceeding with channels download without decodeKey; encrypted payload will be kept as-is: %s",
                normalized_url[:120],
            )
        requested_auto_decrypt = (
            bool(_runtime_config.get("auto_decrypt", True))
            if request.auto_decrypt is None
            else bool(request.auto_decrypt)
        )
        auto_decrypt = bool(requested_auto_decrypt and decode_key)
        if request.auto_decrypt and request.decryption_key and not decode_key:
            logger.warning(
                "Ignore non-numeric decryption_key in /api/channels/download: %s",
                str(request.decryption_key)[:32],
            )
        logger.info(
            "Channels download request: requiresKey=%s requestedDecodeKey=%s detectedDecodeKey=%s effectiveDecodeKey=%s autoDecryptRequested=%s autoDecryptEffective=%s placeholder=%s title=%s url=%s",
            "yes" if requires_decode_key else "no",
            "yes" if requested_decode_key else "no",
            "yes" if detected_decode_key else "no",
            "yes" if decode_key else "no",
            "yes" if requested_auto_decrypt else "no",
            "yes" if auto_decrypt else "no",
            "yes" if (detected_video and _collect_video_placeholder_reasons(detected_video)) else "no",
            _preview_log_value(getattr(detected_video, "title", None) or _resolve_task_title(normalized_url), 72),
            _preview_log_value(normalized_url, 144),
        )

        downloader = get_downloader()
        quality = request.quality or _runtime_config.get("quality_preference") or "best"
        task_id = f"channels_{uuid.uuid4().hex}"
        task_title = _resolve_task_title(normalized_url)
        task_thumbnail = detected_video.thumbnail if detected_video else None
        preferred_output_path = request.output_path
        if not preferred_output_path and _runtime_config.get("download_dir"):
            preferred_output_path = str(_runtime_config.get("download_dir"))

        effective_output_path = _resolve_download_output_path(
            normalized_url,
            task_title,
            preferred_output_path,
        )
        task_output_path = str(Path(effective_output_path).parent) if effective_output_path else str(downloader.output_dir)

        async with AsyncSessionLocal() as session:
            task = DownloadTask(
                task_id=task_id,
                url=normalized_url,
                title=task_title,
                platform="weixin_channels",
                thumbnail=task_thumbnail,
                duration=getattr(detected_video, "duration", None) if detected_video else None,
                quality=quality,
                output_path=task_output_path,
                status="pending",
                progress=0.0,
            )
            session.add(task)
            await session.commit()

        _download_tasks[task_id] = asyncio.create_task(
            _run_download_task(
                task_id,
                url=normalized_url,
                quality=quality,
                output_path=effective_output_path,
                auto_decrypt=auto_decrypt,
                decryption_key=decode_key,
                title=task_title,
            )
        )
        _attach_download_task_callback(task_id)

        return {
            "success": True,
            "task_id": task_id,
            "file_path": None,
            "file_size": None,
            "error": None,
            "error_code": None,
            "message": "下载任务已创建",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        raise HTTPException(status_code=500, detail=f"下载视频失败: {str(e)}")


@router.post("/download/cancel")
async def cancel_download(request: CancelDownloadRequest):
    """取消下载"""
    try:
        task_id = (request.task_id or "").strip()
        if not task_id:
            raise HTTPException(status_code=400, detail="task_id 不能为空")

        active_task = _download_tasks.get(task_id)
        if active_task and not active_task.done():
            active_task.cancel()

        try:
            get_downloader().cancel_download(task_id)
        except Exception:
            logger.debug("cancel_download failed for %s", task_id, exc_info=True)

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(DownloadTask).where(DownloadTask.task_id == task_id))
            task = result.scalar_one_or_none()
            if task is None:
                return {"success": False, "message": "任务不存在"}

            if task.status in {"completed", "encrypted", "failed", "cancelled"}:
                return {"success": False, "message": f"任务当前状态为 {task.status}，无需取消"}

            task.status = "cancelled"
            task.completed_at = datetime.utcnow()
            task.error_message = "用户取消下载"
            await session.commit()

        return {"success": True, "message": "下载已取消"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error canceling download: {e}")
        raise HTTPException(status_code=500, detail=f"取消下载失败: {str(e)}")


@router.get("/download/tasks")
async def get_download_tasks():
    """获取下载任务列表"""
    try:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(DownloadTask)
                .where(
                    or_(
                        DownloadTask.platform.in_(_CHANNEL_TASK_PLATFORMS),
                        DownloadTask.task_id.like("channels_%"),
                    )
                )
                .order_by(desc(DownloadTask.created_at), desc(DownloadTask.id))
                .limit(200)
            )
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            return _prepare_download_task_payloads(tasks)
    except Exception as e:
        logger.error(f"Error getting download tasks: {e}")
        raise HTTPException(status_code=500, detail=f"获取下载任务失败: {str(e)}")


@router.delete("/download/tasks/{task_id}")
async def delete_download_task(task_id: str):
    """删除下载任务"""
    try:
        if not task_id:
            raise HTTPException(status_code=400, detail="task_id 不能为空")

        active_task = _download_tasks.get(task_id)
        if active_task and not active_task.done():
            raise HTTPException(status_code=409, detail="任务正在下载中，请先取消任务")

        async with AsyncSessionLocal() as session:
            stmt = (
                select(DownloadTask)
                .where(DownloadTask.task_id == task_id)
                .where(
                    or_(
                        DownloadTask.platform.in_(_CHANNEL_TASK_PLATFORMS),
                        DownloadTask.task_id.like("channels_%"),
                    )
                )
            )
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            if task is None:
                return {"success": False, "message": "任务不存在"}

            # 获取文件路径，尝试删除本机文件
            file_path = None
            task_dict = task.to_dict()
            if task_dict.get("file_path"):
                file_path = task_dict["file_path"]

            await session.delete(task)
            await session.commit()

        # 删除本机文件（在线程池中执行，避免阻塞事件循环）
        file_deleted = False
        if file_path:
            def _try_delete_file(fp: str) -> bool:
                from pathlib import Path as _Path
                p = _Path(fp)
                if p.exists() and p.is_file():
                    p.unlink()
                    return True
                return False
            try:
                file_deleted = await asyncio.to_thread(_try_delete_file, file_path)
                if file_deleted:
                    logger.info(f"已删除本机文件: {file_path}")
            except Exception as e:
                logger.warning(f"删除本机文件失败: {file_path}, 错误: {e}")

        _download_tasks.pop(task_id, None)
        msg = "任务和文件已删除" if file_deleted else "任务已删除"
        return {"success": True, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting download task: {e}")
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")


# ==================== 证书管理 API ====================

@router.get("/certificate")
async def get_cert_info():
    """获取证书信息"""
    try:
        info = await asyncio.to_thread(get_cert_installer().get_cert_info)
        return {
            "exists": info.get("cert_exists", False),
            "valid": info.get("cert_installed", False),
            "expires_at": None,
            "fingerprint": None,
            "path": info.get("cert_file"),
            "root_installed": info.get("cert_installed", False),
            "wechat_p12_path": info.get("cert_p12_file"),
            "wechat_p12_exists": info.get("cert_p12_exists", False),
            "wechat_p12_installed": info.get("wechat_p12_installed", False),
            "wechat_p12_subject_present": info.get("wechat_p12_subject_present", False),
            "wechat_p12_sources": info.get("wechat_p12_sources", []),
            "recommended_format": info.get("preferred_download_format", "p12"),
        }
    except Exception as e:
        logger.error(f"Error getting cert info: {e}")
        raise HTTPException(status_code=500, detail=f"获取证书信息失败: {str(e)}")


@router.post("/certificate/generate")
async def generate_cert():
    """生成证书"""
    try:
        installer = get_cert_installer()
        success = await asyncio.to_thread(installer.ensure_cert_exists)
        info = await asyncio.to_thread(installer.get_cert_info)
        error_detail = getattr(installer, 'last_error', None) or "证书生成失败"
        return {
            "success": success,
            "cert_path": str(installer.cert_file) if installer.cert_file.exists() else None,
            "wechat_p12_path": str(info.get("cert_p12_file")) if info.get("cert_p12_exists") else None,
            "wechat_p12_sources": info.get("wechat_p12_sources", []),
            "error_message": None if success else error_detail,
        }
    except Exception as e:
        logger.error(f"Error generating cert: {e}")
        raise HTTPException(status_code=500, detail=f"生成证书失败: {str(e)}")


@router.post("/certificate/export")
async def export_cert(request: CertificateExportRequest):
    """导出证书"""
    try:
        installer = get_cert_installer()
        if not await asyncio.to_thread(installer.ensure_cert_exists):
            return {"success": False, "message": "证书不存在", "path": None}

        cert_format, source = installer.get_export_source(request.format)
        if not source.exists():
            return {"success": False, "message": f"{cert_format.upper()} 证书不存在", "path": None}

        target = _validate_certificate_export_target(request.export_path, cert_format)
        await asyncio.to_thread(target.write_bytes, source.read_bytes())
        return {"success": True, "message": "证书已导出", "path": str(target)}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting cert: {e}")
        raise HTTPException(status_code=500, detail=f"导出证书失败: {str(e)}")


@router.get("/certificate/download")
async def download_cert(format: str = Query("p12")):
    """下载 mitmproxy 证书文件。"""
    try:
        installer = get_cert_installer()
        if not await asyncio.to_thread(installer.ensure_cert_exists):
            raise HTTPException(status_code=404, detail="证书不存在")

        cert_format, source = installer.get_export_source(format)
        if not source.exists():
            raise HTTPException(status_code=404, detail=f"{cert_format.upper()} 证书不存在")

        media_type = "application/x-pkcs12" if cert_format == "p12" else "application/pkix-cert"
        return FileResponse(
            path=str(source),
            media_type=media_type,
            filename=source.name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading cert: {e}")
        raise HTTPException(status_code=500, detail=f"下载证书失败: {str(e)}")


@router.post("/certificate/install-root")
async def install_root_cert():
    """安装 Windows 根证书。"""
    try:
        installer = get_cert_installer()
        cert_exists = await asyncio.to_thread(installer.ensure_cert_exists)
        if not cert_exists:
            detail = getattr(installer, 'last_error', None) or "请先点击「生成证书」"
            return {
                "success": False,
                "message": f"证书文件未生成: {detail}",
                "root_installed": False,
                "wechat_p12_installed": False,
            }
        success = await asyncio.to_thread(installer.install_cert)
        info = await asyncio.to_thread(installer.get_cert_info)
        fail_msg = getattr(installer, 'last_error', None) or "系统根证书安装失败，请在弹出的 UAC 窗口中点击「是」授权"
        return {
            "success": success,
            "message": "系统根证书已安装" if success else fail_msg,
            "root_installed": info.get("cert_installed", False),
            "wechat_p12_installed": info.get("wechat_p12_installed", False),
        }
    except Exception as e:
        logger.error(f"Error installing root cert: {e}")
        raise HTTPException(status_code=500, detail=f"安装系统根证书失败: {str(e)}")


@router.post("/certificate/install-wechat-p12")
async def install_wechat_p12():
    """导入 WeChat 4.x 更兼容的 P12。"""
    try:
        installer = get_cert_installer()
        cert_exists = await asyncio.to_thread(installer.ensure_cert_exists)
        if not cert_exists:
            detail = getattr(installer, 'last_error', None) or "请先点击「生成证书」"
            return {
                "success": False,
                "message": f"证书文件未生成: {detail}",
                "root_installed": False,
                "wechat_p12_installed": False,
            }
        success = await asyncio.to_thread(installer.install_wechat_p12)
        info = await asyncio.to_thread(installer.get_cert_info)
        return {
            "success": success,
            "message": "微信兼容 P12 已导入" if success else "微信兼容 P12 导入失败",
            "root_installed": info.get("cert_installed", False),
            "wechat_p12_installed": info.get("wechat_p12_installed", False),
        }
    except Exception as e:
        logger.error(f"Error installing WeChat P12: {e}")
        raise HTTPException(status_code=500, detail=f"导入微信兼容 P12 失败: {str(e)}")


@router.get("/certificate/instructions")
async def get_cert_instructions():
    """获取证书安装说明"""
    try:
        return {
            "instructions": (
                "1. 先生成证书，确认同时存在 mitmproxy-ca-cert.cer、mitmproxy-ca.p12 和 mitmproxy-ca-cert.p12。\n"
                "2. 安装系统根证书：把 mitmproxy-ca-cert.cer 导入 Windows“受信任的根证书颁发机构”。\n"
                "3. 微信 4.x 兼容模式优先导入 mitmproxy-ca.p12；它包含私钥。"
                "为了兼容部分机型，也建议把 mitmproxy-ca-cert.p12 一并导入“当前用户 -> 个人”证书库；密码留空即可。\n"
                "4. 证书安装或导入完成后，必须完全退出微信（包括 Weixin.exe / WeChatAppEx.exe）再重新打开。\n"
                "5. 然后重新进入视频号页面，并把目标视频完整播放一遍；否则标题、缩略图和 decodeKey 仍可能拿不到。"
            )
        }
    except Exception as e:
        logger.error(f"Error getting cert instructions: {e}")
        raise HTTPException(status_code=500, detail=f"获取证书说明失败: {str(e)}")


# ==================== 配置管理 API ====================

@router.get("/config")
async def get_config():
    """获取配置"""
    try:
        return dict(_runtime_config)
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("/config")
async def update_config(config: ConfigUpdate):
    """更新配置"""
    try:
        if config.proxy_port is not None:
            _runtime_config["proxy_port"] = int(config.proxy_port)
        if config.download_dir is not None:
            _runtime_config["download_dir"] = config.download_dir
        if config.auto_decrypt is not None:
            _runtime_config["auto_decrypt"] = bool(config.auto_decrypt)
        if config.auto_clean_wechat_cache is not None:
            _runtime_config["auto_clean_wechat_cache"] = bool(config.auto_clean_wechat_cache)
        if config.quality_preference is not None:
            _runtime_config["quality_preference"] = config.quality_preference
        if config.clear_on_exit is not None:
            _runtime_config["clear_on_exit"] = bool(config.clear_on_exit)
        return {"success": True, "message": "配置已更新"}
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


# ==================== 驱动管理 API ====================

@router.get("/driver/status")
async def get_driver_status():
    """获取驱动状态"""
    try:
        status = await asyncio.to_thread(get_driver_manager().get_status)
        return status.to_dict()
    except Exception as e:
        logger.error(f"Error getting driver status: {e}")
        raise HTTPException(status_code=500, detail=f"获取驱动状态失败: {str(e)}")


@router.post("/driver/install")
async def install_driver():
    """安装驱动（自动从 GitHub 下载 WinDivert）"""
    try:
        manager = get_driver_manager()
        # 优先使用自动下载安装，会自动检测是否已安装
        result = await manager.download_and_install()
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error installing driver: {e}")
        raise HTTPException(status_code=500, detail=f"安装驱动失败: {str(e)}")


@router.post("/driver/request-admin")
async def request_admin_restart():
    """请求管理员权限重启"""
    try:
        success = await asyncio.to_thread(get_driver_manager().request_admin_restart)
        return {
            "success": success,
            "message": "已请求管理员权限" if success else "请求管理员权限失败",
        }
    except Exception as e:
        logger.error(f"Error requesting admin restart: {e}")
        raise HTTPException(status_code=500, detail=f"请求管理员权限失败: {str(e)}")


# ==================== 捕获配置 API ====================

@router.get("/capture/config")
async def get_capture_config():
    """获取捕获配置"""
    try:
        return _capture_config.to_dict()
    except Exception as e:
        logger.error(f"Error getting capture config: {e}")
        raise HTTPException(status_code=500, detail=f"获取捕获配置失败: {str(e)}")


@router.put("/capture/config")
async def update_capture_config(
    capture_mode: Optional[str] = Body(None),
    use_windivert: Optional[bool] = Body(None),
    quic_blocking_enabled: Optional[bool] = Body(None),
    target_processes: Optional[List[str]] = Body(None),
    no_detection_timeout: Optional[int] = Body(None),
    log_unrecognized_domains: Optional[bool] = Body(None)
):
    """更新捕获配置"""
    try:
        if capture_mode is not None:
            _capture_config.capture_mode = _normalize_capture_mode(capture_mode)
        if use_windivert is not None:
            _capture_config.use_windivert = use_windivert
        if quic_blocking_enabled is not None:
            _capture_config.quic_blocking_enabled = quic_blocking_enabled
        if target_processes is not None:
            _capture_config.target_processes = _resolve_target_processes(target_processes)
        if no_detection_timeout is not None:
            _capture_config.no_detection_timeout = no_detection_timeout
        if log_unrecognized_domains is not None:
            _capture_config.log_unrecognized_domains = log_unrecognized_domains

        if _sniffer is not None:
            _sniffer.quic_blocking_enabled = _capture_config.quic_blocking_enabled
            _sniffer.set_target_processes(_resolve_target_processes(_capture_config.target_processes))
            if quic_blocking_enabled is not None and _sniffer.transparent_mode and _sniffer.is_running:
                await _sniffer.toggle_quic_blocking(_capture_config.quic_blocking_enabled)

        return {"success": True, "message": "捕获配置已更新"}
    except Exception as e:
        logger.error(f"Error updating capture config: {e}")
        raise HTTPException(status_code=500, detail=f"更新捕获配置失败: {str(e)}")


@router.get("/quic/status")
async def get_quic_status():
    """获取 QUIC 阻止状态。"""
    try:
        return get_sniffer().get_quic_status()
    except Exception as e:
        logger.error(f"Error getting QUIC status: {e}")
        raise HTTPException(status_code=500, detail=f"获取 QUIC 状态失败: {str(e)}")


@router.post("/quic/toggle")
async def toggle_quic(request: QUICToggleRequest):
    """切换 QUIC 阻止状态。"""
    try:
        _capture_config.quic_blocking_enabled = bool(request.enabled)
        sniffer = get_sniffer()
        return await sniffer.toggle_quic_blocking(_capture_config.quic_blocking_enabled)
    except Exception as e:
        logger.error(f"Error toggling QUIC blocking: {e}")
        raise HTTPException(status_code=500, detail=f"切换 QUIC 阻止失败: {str(e)}")


@router.get("/capture/statistics")
async def get_capture_statistics():
    """获取捕获统计"""
    try:
        sniffer = get_sniffer()
        status = sniffer.get_status()
        return {
            "state": status.state.value,
            "mode": _capture_config.capture_mode.value,
            "statistics": _build_capture_statistics(sniffer),
            "started_at": status.started_at.isoformat() if status.started_at else None,
        }
    except Exception as e:
        logger.error(f"Error getting capture statistics: {e}")
        raise HTTPException(status_code=500, detail=f"获取捕获统计失败: {str(e)}")


@router.get("/proxy/detect")
async def detect_proxy():
    """探测当前代理环境。"""
    try:
        proxy_info = await _detect_proxy_info()
        warning = _build_proxy_environment_warning(proxy_info)
        payload = proxy_info.to_dict()
        payload["warning"] = warning
        return payload
    except Exception as e:
        logger.error(f"Error detecting proxy: {e}")
        raise HTTPException(status_code=500, detail=f"探测代理环境失败: {str(e)}")


def _detect_admin_status() -> bool:
    """检测当前进程是否具有管理员权限。"""
    if sys.platform == "win32":
        try:
            import ctypes

            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            logger.debug("Failed to detect admin status on Windows", exc_info=True)
            return False

    geteuid = getattr(os, "geteuid", None)
    if callable(geteuid):
        try:
            return geteuid() == 0
        except Exception:
            logger.debug("Failed to detect admin status via geteuid", exc_info=True)
    return False


def _collect_wechat_processes() -> List[Dict[str, Any]]:
    """收集微信相关进程信息。"""
    import psutil

    processes: List[Dict[str, Any]] = []
    now = datetime.utcnow().isoformat() + "Z"

    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            name = proc.info.get("name")
            normalized_name = str(name or "").strip().lower()
            helper_match = normalized_name in _HELPER_PROCESS_NAME_SET
            if not name or (
                not helper_match
                and not any(keyword in normalized_name for keyword in ("wechat", "weixin"))
            ):
                continue

            ports: List[int] = []
            try:
                ports = sorted(
                    {
                        int(conn.laddr.port)
                        for conn in proc.connections(kind="inet")
                        if getattr(conn, "laddr", None) and getattr(conn.laddr, "port", None)
                    }
                )[:20]
            except Exception:
                logger.debug("Failed to inspect WeChat process ports", exc_info=True)

            processes.append(
                {
                    "pid": proc.info.get("pid"),
                    "name": name,
                    "exe": proc.info.get("exe"),
                    "exe_path": proc.info.get("exe"),
                    "ports": ports,
                    "last_seen": now,
                }
            )
        except Exception:
            logger.debug("Failed to inspect WeChat process", exc_info=True)

    return processes


def _split_detected_hosts(top_hosts: List[Any]) -> Dict[str, List[str]]:
    """将运行时主机列表拆分为域名和 IP 两类。"""
    detected_snis: List[str] = []
    detected_ips: List[str] = []

    for item in top_hosts:
        host = item[0] if isinstance(item, (list, tuple)) and item else str(item)
        if not host:
            continue
        if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", str(host)):
            detected_ips.append(str(host))
        else:
            detected_snis.append(str(host))

    return {
        "detected_snis": detected_snis,
        "detected_ips": detected_ips,
    }


def _dedupe_messages(messages: List[str]) -> List[str]:
    """按顺序去重消息列表。"""
    seen = set()
    result: List[str] = []
    for message in messages:
        text = str(message or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _get_channels_log_file() -> Path:
    """返回 channels 诊断使用的日志文件路径。"""
    return get_data_dir() / "logs" / "app.log"


def _shorten_text(text: str, limit: int = 240) -> str:
    """裁剪过长日志，避免诊断接口返回巨大字符串。"""
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _format_channels_log_line(line: str) -> str:
    """将原始日志压缩成前端更易阅读的一行。"""
    parts = str(line or "").strip().split(" - ", 3)
    if len(parts) < 4:
        return _shorten_text(line)

    timestamp, logger_name, level, message = parts
    time_part = timestamp.split(" ", 1)[1] if " " in timestamp else timestamp
    short_logger = logger_name.split(".")[-1]
    return _shorten_text(f"{time_part} {level} {short_logger}: {message}")


def _read_recent_channels_log_summary(
    tail_lines: int = 1500,
    match_limit: int = 40,
    critical_limit: int = 10,
) -> Dict[str, Any]:
    """读取最近的 channels 相关日志，供诊断接口直接返回。"""
    log_file = _get_channels_log_file()
    summary: Dict[str, Any] = {
        "log_file": str(log_file),
        "lines": [],
        "critical_messages": [],
    }
    if not log_file.exists():
        return summary

    try:
        with log_file.open("r", encoding="utf-8", errors="ignore") as handle:
            tail = list(deque(handle, maxlen=tail_lines))

        matched_lines: List[str] = []
        critical_lines: List[str] = []
        for raw_line in tail:
            line = raw_line.strip()
            if not line or not any(marker in line for marker in _CHANNELS_DIAGNOSTIC_LOG_MARKERS):
                continue

            formatted = _format_channels_log_line(line)
            if not formatted:
                continue

            matched_lines.append(formatted)
            if any(marker in line for marker in _CHANNELS_DIAGNOSTIC_CRITICAL_MARKERS):
                critical_lines.append(formatted)

        summary["lines"] = _dedupe_messages(matched_lines)[-match_limit:]
        summary["critical_messages"] = _dedupe_messages(critical_lines)[-critical_limit:]
        return summary
    except Exception:
        logger.debug("Failed to read recent channels diagnostic logs", exc_info=True)
        summary["critical_messages"] = [
            f"无法读取 channels 诊断日志，请检查: {log_file}"
        ]
        return summary


async def _build_frontend_diagnostics_payload() -> Dict[str, Any]:
    """构造前端 DiagnosticsPanel 所需的数据结构。"""
    sniffer = get_sniffer()
    runtime = sniffer.get_runtime_statistics()
    statistics = _build_capture_statistics(sniffer)
    host_split = _split_detected_hosts(runtime.get("top_hosts", []))
    proxy_info = await _detect_proxy_info()
    proxy_warning = _build_proxy_environment_warning(proxy_info)
    cert_warning = _build_channels_certificate_warning(await asyncio.to_thread(get_cert_installer().get_cert_info))
    status = sniffer.get_status()
    is_admin = _detect_admin_status()
    wechat_processes = await asyncio.to_thread(_collect_wechat_processes)
    log_summary = await asyncio.to_thread(_read_recent_channels_log_summary)
    recommendations = _generate_recommendations(
        is_admin,
        len(wechat_processes) > 0,
        status.state.value,
        status.videos_detected,
    )

    recent_errors: List[str] = []
    if status.error_message:
        recent_errors.append(status.error_message)
    if proxy_warning:
        recent_errors.append(proxy_warning)
    if cert_warning:
        recent_errors.append(cert_warning)
    for recommendation in recommendations:
        level = recommendation.get("level")
        if level in {"error", "warning"}:
            message = recommendation.get("message")
            action = recommendation.get("action")
            if message and action:
                recent_errors.append(f"{message}：{action}")
            elif message:
                recent_errors.append(str(message))
    recent_errors.extend(log_summary["critical_messages"])
    if (
        statistics.get("renderer_recycle_attempted")
        and not statistics.get("channels_page_injection_at")
    ):
        recent_errors.append(
            "已检测到视频号页面可能在嗅探启动前就已打开。VidFlow 已尝试安全刷新微信页面渲染进程；"
            "如果当前仍未捕获到页面请求，说明视频号页面还没有重新走代理链路。"
        )
    elif (
        status.state.value == "running"
        and statistics.get("videos_detected", 0) > 0
        and not statistics.get("channels_page_injection_at")
    ):
        recent_errors.append(
            "当前已抓到视频分片，但尚未捕获到视频号页面注入；这通常意味着页面比嗅探器更早打开。"
        )

    return {
        "detected_snis": host_split["detected_snis"],
        "detected_ips": host_split["detected_ips"],
        "wechat_processes": wechat_processes,
        "proxy_info": proxy_info.to_dict(),
        "recent_errors": _dedupe_messages(recent_errors),
        "capture_log": log_summary["lines"],
        "recent_response_samples": runtime.get("recent_response_samples", []),
        "statistics": {
            **statistics,
            "is_admin": is_admin,
            "wechat_processes": len(wechat_processes),
            "sniffer_state": status.state.value,
            "diagnostic_log_file": log_summary["log_file"],
            "diagnostic_log_matches": len(log_summary["lines"]),
        },
    }


@router.get("/diagnostics")
async def get_diagnostics():
    """返回前端诊断面板使用的结构化诊断信息。"""
    try:
        return await _build_frontend_diagnostics_payload()
    except Exception as e:
        logger.error(f"Error getting diagnostics: {e}")
        raise HTTPException(status_code=500, detail=f"获取诊断信息失败: {str(e)}")


@router.get("/diagnose")
async def diagnose_system():
    """诊断系统状态"""
    try:
        is_admin = _detect_admin_status()
        wechat_processes = _collect_wechat_processes()

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
