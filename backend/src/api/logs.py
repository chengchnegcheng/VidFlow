"""
日志管理 API
"""
import os
import re
import sys
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends, Request, Header, status
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel
import aiofiles

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])
logger = logging.getLogger(__name__)

# 日志文件路径（与 main.py 保持一致）
if getattr(sys, 'frozen', False):
    # 打包后：使用用户数据目录
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        BASE_DIR = Path(appdata) / 'VidFlow'
    elif sys.platform == 'darwin':
        BASE_DIR = Path.home() / 'Library' / 'Application Support' / 'VidFlow'
    else:
        BASE_DIR = Path.home() / '.local' / 'share' / 'VidFlow'
else:
    BASE_DIR = Path(__file__).parent.parent.parent
LOGS_DIR = BASE_DIR / "data" / "logs"
LOG_FILE = LOGS_DIR / "app.log"

# 日志行起始模式：以时间戳开头 (2025-10-26 01:53:12,123)
_LOG_LINE_START = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')

# 尾部读取默认大小（1MB，足够容纳数千条日志）
_TAIL_READ_BYTES = 1024 * 1024


class LogEntry(BaseModel):
    """日志条目"""
    timestamp: str
    level: str
    logger: str
    message: str
    line_number: int


class LogStats(BaseModel):
    """日志统计"""
    total_lines: int
    error_count: int
    warning_count: int
    info_count: int
    debug_count: int
    file_size: int
    last_modified: str


# 统计缓存（避免频繁读取大文件）
_stats_cache: Optional[LogStats] = None
_stats_cache_mtime: Optional[float] = None


async def _read_file_tail(file_path: Path, max_bytes: int = _TAIL_READ_BYTES) -> tuple[str, int]:
    """从文件尾部读取内容，避免全量加载大文件

    Args:
        file_path: 日志文件路径
        max_bytes: 最大读取字节数

    Returns:
        (文本内容, 估算的跳过行数)
    """
    file_size = file_path.stat().st_size
    if file_size <= max_bytes:
        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return await f.read(), 0

    # 从尾部读取
    async with aiofiles.open(file_path, 'rb') as f:
        await f.seek(-max_bytes, 2)
        raw = await f.read()

    text = raw.decode('utf-8', errors='ignore')
    # 丢弃第一个不完整的行
    first_newline = text.find('\n')
    if first_newline >= 0:
        text = text[first_newline + 1:]

    # 估算跳过的行数
    lines_in_text = text.count('\n') + 1
    avg_line_len = max(1, len(text) / max(1, lines_in_text))
    skipped_bytes = file_size - max_bytes
    estimated_skipped = int(skipped_bytes / avg_line_len)

    return text, estimated_skipped


def _merge_multiline(raw_lines: list[str], line_offset: int = 0) -> list[tuple[str, int]]:
    """将续行（堆栈跟踪等）合并到所属的日志条目

    返回 (合并后的文本, 起始行号) 列表
    """
    entries: list[tuple[str, int]] = []
    current_text: Optional[str] = None
    current_line_no = 0

    for i, line in enumerate(raw_lines):
        stripped = line.rstrip('\n\r')
        if not stripped:
            continue

        if _LOG_LINE_START.match(stripped):
            # 新日志条目开始 → 保存上一条
            if current_text is not None:
                entries.append((current_text, current_line_no))
            current_text = stripped
            current_line_no = line_offset + i
        elif current_text is not None:
            # 续行（traceback / 多行消息），追加到当前条目
            current_text += '\n' + stripped

    # 保存最后一条
    if current_text is not None:
        entries.append((current_text, current_line_no))

    return entries


def _parse_entry(text: str, line_number: int) -> Optional[LogEntry]:
    """解析单条日志（支持多行消息）"""
    try:
        first_line, *rest = text.split('\n', 1)
        parts = first_line.split(' - ', 3)
        if len(parts) < 4:
            return None

        message = parts[3].strip()
        if rest:
            message += '\n' + rest[0]

        return LogEntry(
            timestamp=parts[0].strip(),
            logger=parts[1].strip(),
            level=parts[2].strip(),
            message=message,
            line_number=line_number,
        )
    except Exception:
        return None


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def verify_log_access(
    request: Request,
    api_key: Optional[str] = Query(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None),
):
    client_host = request.client.host if request.client else "127.0.0.1"
    if client_host in ("127.0.0.1", "::1"):
        return True

    expected_key = os.environ.get("VIDFLOW_LOG_API_KEY") or os.environ.get("LOG_API_KEY")
    provided_key = api_key or x_api_key or _extract_bearer_token(authorization)
    if expected_key and provided_key == expected_key:
        return True

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.get("/", response_model=List[LogEntry], dependencies=[Depends(verify_log_access)])
async def get_logs(
    limit: int = Query(default=100, description="返回的日志条数"),
    level: Optional[str] = Query(default=None, description="日志级别筛选 (INFO, WARNING, ERROR, DEBUG)"),
    search: Optional[str] = Query(default=None, description="搜索关键词"),
    offset: int = Query(default=0, description="偏移量（用于分页）")
):
    """获取日志列表（从尾部读取，最新在前）"""
    try:
        if not LOG_FILE.exists():
            return []

        # 尾部读取，避免加载整个 10MB 文件
        content, line_offset = await _read_file_tail(LOG_FILE)
        raw_lines = content.splitlines()

        # 合并多行日志（堆栈跟踪）
        entries = _merge_multiline(raw_lines, line_offset)

        search_lower = search.lower() if search else None
        logs: list[LogEntry] = []
        need = offset + limit

        # 倒序遍历（最新的在前）
        for text, line_no in reversed(entries):
            entry = _parse_entry(text, line_no)
            if entry is None:
                continue

            if level and entry.level != level:
                continue

            if search_lower:
                if (search_lower not in entry.message.lower()
                        and search_lower not in entry.logger.lower()):
                    continue

            logs.append(entry)
            if len(logs) >= need:
                break

        return logs[offset:offset + limit]

    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")


@router.get("/stats", response_model=LogStats, dependencies=[Depends(verify_log_access)])
async def get_log_stats():
    """获取日志统计信息（带缓存优化）"""
    global _stats_cache, _stats_cache_mtime

    try:
        if not LOG_FILE.exists():
            return LogStats(
                total_lines=0,
                error_count=0,
                warning_count=0,
                info_count=0,
                debug_count=0,
                file_size=0,
                last_modified=""
            )

        # 获取文件修改时间
        file_stat = os.stat(LOG_FILE)
        current_mtime = file_stat.st_mtime

        # 如果文件未变化且有缓存，直接返回缓存
        if _stats_cache is not None and _stats_cache_mtime == current_mtime:
            return _stats_cache

        # 统计日志 - 逐行扫描，已有缓存机制不会频繁执行
        error_count = 0
        warning_count = 0
        info_count = 0
        debug_count = 0
        total_lines = 0

        async with aiofiles.open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            async for line in f:
                total_lines += 1
                if ' - ERROR - ' in line:
                    error_count += 1
                elif ' - WARNING - ' in line:
                    warning_count += 1
                elif ' - INFO - ' in line:
                    info_count += 1
                elif ' - DEBUG - ' in line:
                    debug_count += 1

        # 返回可读的 ISO 格式日期
        last_modified_str = datetime.fromtimestamp(current_mtime).strftime('%Y-%m-%d %H:%M:%S')

        result = LogStats(
            total_lines=total_lines,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            debug_count=debug_count,
            file_size=file_stat.st_size,
            last_modified=last_modified_str,
        )

        # 更新缓存
        _stats_cache = result
        _stats_cache_mtime = current_mtime

        return result

    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.delete("/clear", dependencies=[Depends(verify_log_access)])
async def clear_logs():
    """清空日志文件"""
    global _stats_cache, _stats_cache_mtime

    try:
        if LOG_FILE.exists():
            async with aiofiles.open(LOG_FILE, 'w', encoding='utf-8', errors='ignore') as f:
                await f.write("")

            _stats_cache = None
            _stats_cache_mtime = None

            return {"success": True, "message": "日志已清空"}
        return {"success": True, "message": "日志文件不存在"}

    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        raise HTTPException(status_code=500, detail=f"清空日志失败: {str(e)}")


@router.get("/download", dependencies=[Depends(verify_log_access)])
async def download_logs():
    """下载日志文件"""
    try:
        if not LOG_FILE.exists():
            raise HTTPException(status_code=404, detail="日志文件不存在")

        return FileResponse(
            path=LOG_FILE,
            filename=f"vidflow_logs_{Path(LOG_FILE).stem}.log",
            media_type="text/plain"
        )

    except Exception as e:
        logger.error(f"Error downloading logs: {e}")
        raise HTTPException(status_code=500, detail=f"下载日志失败: {str(e)}")


@router.get("/path", dependencies=[Depends(verify_log_access)])
async def get_log_path():
    """获取日志文件所在目录路径"""
    try:
        return {
            "success": True,
            "path": str(LOGS_DIR),
            "file": str(LOG_FILE)
        }
    except Exception as e:
        logger.error(f"Error getting log path: {e}")
        raise HTTPException(status_code=500, detail=f"获取日志路径失败: {str(e)}")


@router.get("/tail", dependencies=[Depends(verify_log_access)])
async def tail_logs(lines: int = 50):
    """获取最新的 N 条日志（尾部读取）"""
    try:
        if not LOG_FILE.exists():
            return []

        # 尾部读取（256KB 足够 50 条）
        content, line_offset = await _read_file_tail(LOG_FILE, max_bytes=256 * 1024)
        raw_lines = content.splitlines()
        entries = _merge_multiline(raw_lines, line_offset)

        # 只取最后 N 条
        tail_entries = entries[-lines:] if len(entries) > lines else entries

        logs: list[LogEntry] = []
        for text, line_no in tail_entries:
            entry = _parse_entry(text, line_no)
            if entry:
                logs.append(entry)

        return logs

    except Exception as e:
        logger.error(f"Error tailing logs: {e}")
        raise HTTPException(status_code=500, detail=f"获取日志失败: {str(e)}")
