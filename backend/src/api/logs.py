"""
日志管理 API
"""
import os
import sys
import logging
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

def parse_log_line(line: str, line_number: int) -> Optional[LogEntry]:
    """解析日志行"""
    try:
        # 格式: 2025-10-26 01:53:12,123 - logger_name - LEVEL - message
        parts = line.split(' - ', 3)
        if len(parts) >= 4:
            return LogEntry(
                timestamp=parts[0].strip(),
                logger=parts[1].strip(),
                level=parts[2].strip(),
                message=parts[3].strip(),
                line_number=line_number
            )
    except Exception as e:
        logger.error(f"Failed to parse log line: {e}")
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
    """
    获取日志列表
    
    Args:
        limit: 返回的日志条数
        level: 日志级别筛选 (INFO, WARNING, ERROR, DEBUG)
        search: 搜索关键词（支持搜索消息和logger名称）
        offset: 偏移量（用于分页）
    """
    try:
        if not LOG_FILE.exists():
            return []

        logs = []
        search_lower = search.lower() if search else None

        # 异步读取文件，避免阻塞事件循环
        async with aiofiles.open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            content = await f.read()
            all_lines = content.splitlines(keepends=True)
        
        # 倒序读取（最新的在前）
        for i, line in enumerate(reversed(all_lines)):
            if not line.strip():
                continue
            
            log_entry = parse_log_line(line, len(all_lines) - i - 1)
            if not log_entry:
                continue
            
            # 级别过滤
            if level and log_entry.level != level:
                continue
            
            # 关键词搜索（搜索消息和logger名称）
            if search_lower:
                if search_lower not in log_entry.message.lower() and search_lower not in log_entry.logger.lower():
                    continue
            
            logs.append(log_entry)
            
            # 达到所需数量就停止
            if len(logs) >= (offset + limit):
                break
        
        # 应用偏移和限制
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
        
        # 统计日志 - 使用异步文件读取避免阻塞
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
        
        # 创建统计结果
        result = LogStats(
            total_lines=total_lines,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            debug_count=debug_count,
            file_size=file_stat.st_size,
            last_modified=str(current_mtime)
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
            # 异步清空文件
            async with aiofiles.open(LOG_FILE, 'w', encoding='utf-8', errors='ignore') as f:
                await f.write("")
            
            # 清空统计缓存
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
    """获取最新的N行日志"""
    try:
        if not LOG_FILE.exists():
            return []

        async with aiofiles.open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            content = await f.read()
            all_lines = content.splitlines(keepends=True)
        
        # 获取最后N行
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        logs = []
        for i, line in enumerate(recent_lines):
            if not line.strip():
                continue
            log_entry = parse_log_line(line, len(all_lines) - len(recent_lines) + i)
            if log_entry:
                logs.append(log_entry)
        
        return logs
    
    except Exception as e:
        logger.error(f"Error tailing logs: {e}")
        raise HTTPException(status_code=500, detail=f"获取日志失败: {str(e)}")
