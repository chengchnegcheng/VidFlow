"""
下载任务数据模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.sql import func
from datetime import datetime
from .database import Base


class DownloadTask(Base):
    """下载任务模型"""
    __tablename__ = "download_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String(36), unique=True, index=True, nullable=False)

    # 视频信息
    url = Column(String(500), nullable=False)
    title = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=True)
    thumbnail = Column(String(500), nullable=True)
    duration = Column(Integer, nullable=True)  # 秒

    # 下载配置
    quality = Column(String(50), default="best")
    format_id = Column(String(50), nullable=True)
    output_path = Column(String(500), nullable=True)

    # 状态信息
    status = Column(String(50), default="pending")  # pending, downloading, completed, failed, cancelled
    progress = Column(Float, default=0.0)  # 0-100

    # 下载信息
    downloaded_bytes = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    speed = Column(Float, default=0.0)  # bytes/s
    eta = Column(Integer, default=0)  # seconds

    # 结果信息
    filename = Column(String(500), nullable=True)
    filesize = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        """转换为字典"""
        # 构建完整的文件路径
        file_path = None
        if self.filename:
            from pathlib import Path
            import os

            # 如果 filename 已经是绝对路径，直接使用
            if os.path.isabs(self.filename):
                file_path = self.filename
            # 如果有 output_path,拼接路径
            elif self.output_path:
                file_path = str(Path(self.output_path) / self.filename)
            # 否则使用默认下载目录 (Downloads/VidFlow)
            else:
                from src.core.config_manager import get_default_download_path
                default_path = get_default_download_path()
                file_path = str(Path(default_path) / self.filename)

        # 确保 progress 值在 0-100 范围内
        progress = self.progress if self.progress is not None else 0.0
        progress = max(0.0, min(100.0, progress))

        return {
            'id': self.id,
            'task_id': self.task_id,
            'url': self.url,
            'title': self.title,
            'platform': self.platform,
            'thumbnail': self.thumbnail,
            'duration': self.duration,
            'quality': self.quality,
            'format_id': self.format_id,
            'output_path': self.output_path,
            'status': self.status,
            'progress': progress,
            'downloaded_bytes': self.downloaded_bytes,
            'total_bytes': self.total_bytes,
            'speed': self.speed,
            'eta': self.eta,
            'filename': self.filename,
            'file_path': file_path,  # 添加完整文件路径
            'filesize': self.filesize,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
