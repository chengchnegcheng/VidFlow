"""
字幕任务数据模型
"""
import json
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean
from .database import Base


class BurnSubtitleTask(Base):
    """字幕烧录任务"""
    __tablename__ = "burn_subtitle_tasks"
    
    id = Column(String, primary_key=True)
    video_path = Column(String, nullable=False)
    subtitle_path = Column(String, nullable=False)
    output_path = Column(String, nullable=False)
    video_title = Column(String)
    
    status = Column(String, default="pending")  # pending, burning, completed, failed
    progress = Column(Float, default=0.0)
    error = Column(String, nullable=True)
    cancelled = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """转换为字典"""
        error = self.error
        error_detail = None
        if isinstance(error, str) and error:
            try:
                parsed = json.loads(error)
                if isinstance(parsed, dict) and "code" in parsed and "message" in parsed:
                    error_detail = parsed
                    error = parsed.get("message") or error
            except Exception:
                pass
        return {
            "id": self.id,
            "video_path": self.video_path,
            "subtitle_path": self.subtitle_path,
            "output_path": self.output_path,
            "video_title": self.video_title,
            "status": self.status,
            "progress": self.progress,
            "error": error,
            "error_detail": error_detail,
            "cancelled": self.cancelled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class SubtitleTask(Base):
    """字幕生成任务"""
    __tablename__ = "subtitle_tasks"
    
    id = Column(String, primary_key=True)
    video_path = Column(String, nullable=False)
    video_title = Column(String)
    
    status = Column(String, default="pending")  # pending, processing, completed, failed
    progress = Column(Float, default=0.0)
    
    source_language = Column(String, default="auto")
    target_languages = Column(JSON, default=list)  # ["zh", "en"]
    model = Column(String, default="base")
    formats = Column(JSON, default=list)  # ["srt", "vtt"]
    
    output_files = Column(JSON, default=list)
    error = Column(String, nullable=True)

    cancelled = Column(Boolean, default=False, nullable=False)
    
    detected_language = Column(String, nullable=True)
    segments_count = Column(Integer, default=0)
    duration = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """转换为字典"""
        error = self.error
        error_detail = None
        if isinstance(error, str) and error:
            try:
                parsed = json.loads(error)
                if isinstance(parsed, dict) and "code" in parsed and "message" in parsed:
                    error_detail = parsed
                    error = parsed.get("message") or error
            except Exception:
                pass
        return {
            "id": self.id,
            "video_path": self.video_path,
            "video_title": self.video_title,
            "status": self.status,
            "progress": self.progress,
            "source_language": self.source_language,
            "target_languages": self.target_languages,
            "model": self.model,
            "formats": self.formats,
            "output_files": self.output_files,
            "error": error,
            "error_detail": error_detail,
            "cancelled": self.cancelled,
            "detected_language": self.detected_language,
            "segments_count": self.segments_count,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
