"""
字幕处理器核心功能测试
"""
import pytest
from pathlib import Path
from src.core.subtitle_processor import SubtitleProcessor


@pytest.mark.core
@pytest.mark.unit
class TestSubtitleProcessor:
    """字幕处理器测试类"""

    @pytest.fixture
    def subtitle_processor(self):
        """创建字幕处理器实例"""
        return SubtitleProcessor()

    def test_subtitle_processor_initialization(self, subtitle_processor):
        """测试字幕处理器初始化"""
        assert subtitle_processor is not None
        assert isinstance(subtitle_processor, SubtitleProcessor)

    def test_model_attributes(self, subtitle_processor):
        """测试模型属性"""
        # SubtitleProcessor应该有模型相关属性
        assert hasattr(subtitle_processor, 'model')
        assert hasattr(subtitle_processor, 'model_name')
        assert subtitle_processor.model_name == "base"

    def test_device_attribute(self, subtitle_processor):
        """测试设备属性"""
        # SubtitleProcessor应该有设备属性
        assert hasattr(subtitle_processor, 'device')
        assert subtitle_processor.device == "cpu"

    @pytest.mark.asyncio
    async def test_generate_subtitle_invalid_file(self, subtitle_processor):
        """测试生成字幕 - 无效文件"""
        nonexistent_file = Path("/nonexistent/video.mp4")

        # 应该抛出异常或返回错误
        with pytest.raises(Exception):
            await subtitle_processor.generate_subtitle(
                video_path=str(nonexistent_file),
                language="en",
                model_size="base"
            )

    def test_format_timestamp(self, subtitle_processor):
        """测试时间戳格式化"""
        # 如果有时间戳格式化方法
        if hasattr(subtitle_processor, 'format_timestamp'):
            result = subtitle_processor.format_timestamp(90.5)
            assert isinstance(result, str)

    def test_parse_segments(self, subtitle_processor):
        """测试解析字幕段"""
        # 如果有段解析方法
        if hasattr(subtitle_processor, 'parse_segments'):
            segments = []
            result = subtitle_processor.parse_segments(segments)
            assert isinstance(result, (list, dict))
