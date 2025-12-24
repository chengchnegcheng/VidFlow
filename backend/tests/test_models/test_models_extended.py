"""
数据模型扩展测试
"""
import pytest
from datetime import datetime
from src.models.download import DownloadTask
from src.models.subtitle import SubtitleTask


@pytest.mark.unit
class TestDownloadTaskExtended:
    """下载任务模型扩展测试"""
    
    def test_to_dict_method(self):
        """测试to_dict方法"""
        task = DownloadTask(
            task_id="test-123",
            url="https://example.com/video",
            title="Test Video",
            platform="youtube",
            status="pending"
        )
        
        result = task.to_dict()
        assert isinstance(result, dict)
        assert result["task_id"] == "test-123"
        assert result["url"] == "https://example.com/video"
        assert result["title"] == "Test Video"
        assert result["platform"] == "youtube"
    
    def test_download_task_all_fields(self):
        """测试下载任务所有字段"""
        task = DownloadTask(
            task_id="test-456",
            url="https://example.com/video",
            title="Complete Test",
            platform="youtube",
            thumbnail="https://example.com/thumb.jpg",
            duration=120,
            quality="1080p",
            format_id="137+140",
            output_path="/downloads",
            status="downloading",
            filename="video.mp4",
            filesize=1024000
        )
        
        assert task.task_id == "test-456"
        assert task.title == "Complete Test"
        assert task.thumbnail == "https://example.com/thumb.jpg"
        assert task.duration == 120
        assert task.quality == "1080p"
        assert task.format_id == "137+140"
    
    def test_download_task_status_values(self):
        """测试下载任务状态值"""
        valid_statuses = ["pending", "downloading", "completed", "failed", "cancelled"]
        
        for status in valid_statuses:
            task = DownloadTask(
                task_id=f"test-{status}",
                url="https://example.com/video",
                status=status
            )
            assert task.status == status
    
    def test_download_task_progress_range(self):
        """测试下载任务进度范围"""
        task = DownloadTask(
            task_id="test-progress",
            url="https://example.com/video",
            status="downloading"
        )
        
        # 进度应该在0-100范围内
        task.progress = 0.0
        assert task.progress == 0.0
        
        task.progress = 50.5
        assert task.progress == 50.5
        
        task.progress = 100.0
        assert task.progress == 100.0
    
    def test_download_task_error_message(self):
        """测试下载任务错误消息"""
        task = DownloadTask(
            task_id="test-error",
            url="https://example.com/video",
            status="failed",
            error_message="Network connection failed"
        )
        
        assert task.error_message == "Network connection failed"
    
    def test_to_dict_with_timestamps(self):
        """测试to_dict包含时间戳"""
        task = DownloadTask(
            task_id="test-timestamp",
            url="https://example.com/video",
            status="pending"
        )
        
        result = task.to_dict()
        # created_at和updated_at应该在字典中
        assert "created_at" in result
        assert "updated_at" in result


@pytest.mark.unit
class TestSubtitleTaskExtended:
    """字幕任务模型扩展测试"""
    
    def test_to_dict_method(self):
        """测试to_dict方法"""
        task = SubtitleTask(
            id="sub-123",
            video_path="/path/to/video.mp4",
            source_language="en",
            status="pending"
        )
        
        result = task.to_dict()
        assert isinstance(result, dict)
        assert result["id"] == "sub-123"
        assert result["video_path"] == "/path/to/video.mp4"
        assert result["source_language"] == "en"
    
    def test_subtitle_task_all_fields(self):
        """测试字幕任务所有字段"""
        task = SubtitleTask(
            id="sub-456",
            video_path="/path/to/video.mp4",
            video_title="Test Video",
            source_language="en",
            target_languages=["zh", "ja"],
            model="base",
            formats=["srt", "vtt"],
            status="processing",
            detected_language="en",
            segments_count=100,
            duration=120.5
        )
        
        assert task.id == "sub-456"
        assert task.video_title == "Test Video"
        assert task.target_languages == ["zh", "ja"]
        assert task.model == "base"
        assert task.formats == ["srt", "vtt"]
        assert task.segments_count == 100
        assert task.duration == 120.5
    
    def test_subtitle_task_status_values(self):
        """测试字幕任务状态值"""
        valid_statuses = ["pending", "processing", "completed", "failed"]
        
        for status in valid_statuses:
            task = SubtitleTask(
                id=f"sub-{status}",
                video_path="/path/to/video.mp4",
                status=status
            )
            assert task.status == status
    
    def test_subtitle_task_model_sizes(self):
        """测试字幕任务模型大小"""
        model_sizes = ["tiny", "base", "small", "medium", "large"]
        
        for model_size in model_sizes:
            task = SubtitleTask(
                id=f"sub-model-{model_size}",
                video_path="/path/to/video.mp4",
                model=model_size,
                status="pending"
            )
            assert task.model == model_size
    
    def test_subtitle_task_output_files(self):
        """测试字幕任务输出文件"""
        task = SubtitleTask(
            id="sub-output",
            video_path="/path/to/video.mp4",
            status="completed",
            output_files=[
                "/path/to/video.en.srt",
                "/path/to/video.zh.srt"
            ]
        )
        
        assert isinstance(task.output_files, list)
        assert len(task.output_files) == 2
    
    def test_subtitle_task_error_handling(self):
        """测试字幕任务错误处理"""
        task = SubtitleTask(
            id="sub-error",
            video_path="/path/to/video.mp4",
            status="failed",
            error="Model loading failed"
        )
        
        assert task.error == "Model loading failed"
    
    def test_subtitle_task_progress_tracking(self):
        """测试字幕任务进度跟踪"""
        task = SubtitleTask(
            id="sub-progress",
            video_path="/path/to/video.mp4",
            status="processing"
        )
        
        task.progress = 0.0
        assert task.progress == 0.0 or task.progress is None
        
        task.progress = 75.5
        assert task.progress == 75.5
    
    def test_to_dict_with_all_fields(self):
        """测试to_dict包含所有字段"""
        task = SubtitleTask(
            id="sub-full",
            video_path="/path/to/video.mp4",
            video_title="Full Test",
            source_language="en",
            target_languages=["zh"],
            model="base",
            formats=["srt"],
            status="completed",
            detected_language="en",
            segments_count=50,
            duration=60.0
        )
        
        result = task.to_dict()
        assert "id" in result
        assert "video_path" in result
        assert "video_title" in result
        assert "source_language" in result
        assert "target_languages" in result
        assert "model" in result
        assert "formats" in result
        assert "status" in result
        assert "detected_language" in result
        assert "segments_count" in result
        assert "duration" in result
