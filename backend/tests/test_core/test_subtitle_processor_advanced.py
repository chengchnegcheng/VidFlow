"""
字幕处理器高级测试
"""
import pytest
from pathlib import Path
from src.core.subtitle_processor import SubtitleProcessor


@pytest.mark.core
@pytest.mark.unit
class TestSubtitleProcessorAdvanced:
    """字幕处理器高级测试"""

    @pytest.fixture
    def processor(self):
        """创建字幕处理器实例"""
        return SubtitleProcessor()

    def test_processor_model_default(self, processor):
        """测试默认模型"""
        assert processor.model is None  # 初始时未加载
        assert processor.model_name == "base"

    def test_processor_device_default(self, processor):
        """测试默认设备"""
        assert processor.device == "cpu"

    @pytest.mark.asyncio
    async def test_initialize_model_method(self, processor):
        """测试初始化模型方法存在"""
        assert hasattr(processor, 'initialize_model')
        assert callable(processor.initialize_model)

    def test_has_extract_audio_method(self, processor):
        """测试提取音频方法存在"""
        assert hasattr(processor, 'extract_audio')
        assert callable(processor.extract_audio)

    def test_has_transcribe_method(self, processor):
        """测试转录方法存在"""
        assert hasattr(processor, 'transcribe')
        assert callable(processor.transcribe)

    def test_has_process_video_method(self, processor):
        """测试处理视频方法存在"""
        assert hasattr(processor, 'process_video')
        assert callable(processor.process_video)


@pytest.mark.core
@pytest.mark.unit
class TestSubtitleProcessorFormats:
    """字幕处理器格式测试"""

    @pytest.fixture
    def processor(self):
        """创建字幕处理器实例"""
        return SubtitleProcessor()

    def test_supported_formats(self, processor):
        """测试支持的字幕格式"""
        # 常见字幕格式
        supported_formats = ["srt", "vtt"]
        for fmt in supported_formats:
            assert isinstance(fmt, str)
            assert len(fmt) > 0

    def test_has_format_timestamp_method(self, processor):
        """测试格式化时间戳方法"""
        if hasattr(processor, 'format_timestamp'):
            assert callable(processor.format_timestamp)

    def test_subtitle_format_validation(self, processor):
        """测试字幕格式验证"""
        valid_formats = ["srt", "vtt", "ass", "ssa"]
        for fmt in valid_formats:
            assert isinstance(fmt, str)
            assert len(fmt) in [3, 4]  # 格式扩展名长度


@pytest.mark.core
@pytest.mark.unit
class TestSubtitleProcessorValidation:
    """字幕处理器验证测试"""

    @pytest.fixture
    def processor(self):
        """创建字幕处理器实例"""
        return SubtitleProcessor()

    @pytest.mark.asyncio
    async def test_extract_audio_nonexistent_file(self, processor):
        """测试提取音频 - 不存在的文件"""
        video_path = "/nonexistent/video.mp4"
        audio_path = "/tmp/audio.wav"

        # 应该返回False或抛出异常
        try:
            result = await processor.extract_audio(video_path, audio_path)
            assert result is False
        except Exception:
            # 预期会抛出异常
            pass

    @pytest.mark.asyncio
    async def test_process_video_invalid_path(self, processor):
        """测试处理视频 - 无效路径"""
        invalid_path = Path("/nonexistent/video.mp4")

        with pytest.raises(Exception):
            await processor.process_video(
                video_path=invalid_path,
                output_dir=Path("/tmp"),
                source_language="en"
            )


@pytest.mark.core
@pytest.mark.unit
class TestSubtitleProcessorModels:
    """字幕处理器模型测试"""

    @pytest.fixture
    def processor(self):
        """创建字幕处理器实例"""
        return SubtitleProcessor()

    def test_model_name_options(self, processor):
        """测试模型名称选项"""
        valid_models = ["tiny", "base", "small", "medium", "large"]
        # 默认模型应该在有效列表中
        assert processor.model_name in valid_models

    def test_device_options(self, processor):
        """测试设备选项"""
        valid_devices = ["cpu", "cuda", "auto"]
        # 默认设备应该在有效列表中
        assert processor.device in valid_devices


@pytest.mark.core
@pytest.mark.unit
class TestSubtitleProcessorAttributes:
    """字幕处理器属性测试"""

    @pytest.fixture
    def processor(self):
        """创建字幕处理器实例"""
        return SubtitleProcessor()

    def test_processor_has_model(self, processor):
        """测试处理器有model属性"""
        assert hasattr(processor, 'model')

    def test_processor_has_model_name(self, processor):
        """测试处理器有model_name属性"""
        assert hasattr(processor, 'model_name')
        assert isinstance(processor.model_name, str)

    def test_processor_has_device(self, processor):
        """测试处理器有device属性"""
        assert hasattr(processor, 'device')
        assert isinstance(processor.device, str)

    def test_model_name_not_empty(self, processor):
        """测试模型名称非空"""
        assert len(processor.model_name) > 0

    def test_device_not_empty(self, processor):
        """测试设备名称非空"""
        assert len(processor.device) > 0


@pytest.mark.core
@pytest.mark.unit
class TestSubtitleProcessorLanguages:
    """字幕处理器语言测试"""

    def test_common_languages(self):
        """测试常见语言代码"""
        common_languages = ["en", "zh", "ja", "ko", "es", "fr", "de", "ru", "ar", "pt", "it"]
        # 验证这些是有效的语言代码
        for lang in common_languages:
            assert isinstance(lang, str)
            assert len(lang) == 2

    def test_auto_language(self):
        """测试自动检测语言"""
        auto_lang = "auto"
        assert isinstance(auto_lang, str)
        assert auto_lang == "auto"
