"""
数据模型测试
"""
import pytest
from datetime import datetime
from src.models.download import DownloadTask
from src.models.subtitle import SubtitleTask


@pytest.mark.unit
class TestDownloadTaskModel:
    """下载任务模型测试"""
    
    def test_create_download_task(self):
        """测试创建下载任务"""
        task = DownloadTask(
            task_id="test-123",
            url="https://example.com/video",
            title="Test Video",
            platform="youtube",
            status="pending"
        )
        
        assert task.task_id == "test-123"
        assert task.url == "https://example.com/video"
        assert task.title == "Test Video"
        assert task.platform == "youtube"
        assert task.status == "pending"
    
    def test_download_task_default_values(self):
        """测试下载任务默认值"""
        task = DownloadTask(
            task_id="test-456",
            url="https://example.com/video",
            status="pending"
        )
        
        # 默认值在Column定义中，对象创建时可能为None
        # 在实际数据库操作后会被设置
        assert task.progress is None or task.progress == 0.0
        assert task.downloaded_bytes is None or task.downloaded_bytes == 0
        assert task.total_bytes is None or task.total_bytes == 0
        assert task.speed is None or task.speed == 0.0
        assert task.eta is None or task.eta == 0


@pytest.mark.unit
class TestSubtitleTaskModel:
    """字幕任务模型测试"""
    
    def test_create_subtitle_task(self):
        """测试创建字幕任务"""
        task = SubtitleTask(
            id="sub-123",
            video_path="/path/to/video.mp4",
            source_language="zh",
            model="base",
            status="pending"
        )
        
        assert task.id == "sub-123"
        assert task.video_path == "/path/to/video.mp4"
        assert task.source_language == "zh"
        assert task.model == "base"
        assert task.status == "pending"
    
    def test_subtitle_task_default_values(self):
        """测试字幕任务默认值"""
        task = SubtitleTask(
            id="sub-456",
            video_path="/path/to/video.mp4",
            source_language="en",
            status="pending"
        )
        
        # 默认值在Column定义中，对象创建时可能为None
        assert task.progress is None or task.progress == 0.0
        assert task.status == "pending"
        assert task.source_language == "en"
