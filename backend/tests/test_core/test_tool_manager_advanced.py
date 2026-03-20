"""
工具管理器高级测试
"""
import pytest
from pathlib import Path
from src.core.tool_manager import ToolManager, get_tool_manager, TOOLS_DIR, BIN_DIR, MODELS_DIR


@pytest.mark.core
@pytest.mark.unit
class TestToolManagerAdvanced:
    """工具管理器高级测试类"""

    @pytest.fixture
    def tool_manager(self):
        """创建工具管理器实例"""
        return ToolManager()

    def test_tool_manager_system_detection(self, tool_manager):
        """测试系统检测"""
        assert hasattr(tool_manager, 'system')
        assert tool_manager.system in ['Windows', 'Darwin', 'Linux']

    def test_ffmpeg_path_attribute(self, tool_manager):
        """测试FFmpeg路径属性"""
        assert hasattr(tool_manager, 'ffmpeg_path')
        # 可能是None或Path对象
        assert tool_manager.ffmpeg_path is None or isinstance(tool_manager.ffmpeg_path, Path)

    def test_ytdlp_path_attribute(self, tool_manager):
        """测试yt-dlp路径属性"""
        assert hasattr(tool_manager, 'ytdlp_path')
        # 可能是None或Path对象
        assert tool_manager.ytdlp_path is None or isinstance(tool_manager.ytdlp_path, Path)

    def test_get_ffmpeg_path_returns_string(self, tool_manager):
        """测试获取FFmpeg路径返回字符串"""
        result = tool_manager.get_ffmpeg_path()
        # 应该返回字符串或None
        assert result is None or isinstance(result, str)

    def test_get_ytdlp_path_returns_string(self, tool_manager):
        """测试获取yt-dlp路径返回字符串"""
        result = tool_manager.get_ytdlp_path()
        # 应该返回字符串或None
        assert result is None or isinstance(result, str)

    @pytest.mark.asyncio
    async def test_check_faster_whisper(self, tool_manager):
        """测试检查faster-whisper"""
        result = await tool_manager.check_faster_whisper()
        assert isinstance(result, bool)

    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = get_tool_manager()
        manager2 = get_tool_manager()
        manager3 = get_tool_manager()

        assert manager1 is manager2
        assert manager2 is manager3


@pytest.mark.core
@pytest.mark.unit
class TestToolManagerDirectories:
    """工具管理器目录测试"""

    def test_tools_dir_exists(self):
        """测试工具目录存在"""
        assert TOOLS_DIR.exists()
        assert TOOLS_DIR.is_dir()

    def test_bin_dir_exists(self):
        """测试二进制目录存在"""
        assert BIN_DIR.exists()
        assert BIN_DIR.is_dir()

    def test_models_dir_exists(self):
        """测试模型目录存在"""
        assert MODELS_DIR.exists()
        assert MODELS_DIR.is_dir()

    def test_directory_hierarchy(self):
        """测试目录层次结构"""
        assert BIN_DIR.parent == TOOLS_DIR
        assert MODELS_DIR.parent == TOOLS_DIR

    def test_directory_names(self):
        """测试目录名称"""
        assert TOOLS_DIR.name == "tools"
        assert BIN_DIR.name == "bin"
        assert MODELS_DIR.name == "models"


@pytest.mark.core
@pytest.mark.unit
class TestToolManagerPaths:
    """工具管理器路径测试"""

    @pytest.fixture
    def tool_manager(self):
        """创建工具管理器实例"""
        return ToolManager()

    def test_path_conversion_ffmpeg(self, tool_manager):
        """测试FFmpeg路径转换"""
        path = tool_manager.get_ffmpeg_path()
        if path:
            assert isinstance(path, str)
            assert len(path) > 0

    def test_path_conversion_ytdlp(self, tool_manager):
        """测试yt-dlp路径转换"""
        path = tool_manager.get_ytdlp_path()
        if path:
            assert isinstance(path, str)
            assert len(path) > 0

    def test_path_is_absolute_ffmpeg(self, tool_manager):
        """测试FFmpeg路径是绝对路径"""
        path_str = tool_manager.get_ffmpeg_path()
        if path_str:
            path = Path(path_str)
            assert path.is_absolute()

    def test_path_is_absolute_ytdlp(self, tool_manager):
        """测试yt-dlp路径是绝对路径"""
        path_str = tool_manager.get_ytdlp_path()
        if path_str:
            path = Path(path_str)
            assert path.is_absolute()


@pytest.mark.core
@pytest.mark.unit
class TestToolManagerMethods:
    """工具管理器方法测试"""

    @pytest.fixture
    def tool_manager(self):
        """创建工具管理器实例"""
        return ToolManager()

    def test_has_setup_all_tools_method(self, tool_manager):
        """测试setup_all_tools方法存在"""
        assert hasattr(tool_manager, 'setup_all_tools')
        assert callable(tool_manager.setup_all_tools)

    def test_has_setup_ffmpeg_method(self, tool_manager):
        """测试setup_ffmpeg方法存在"""
        assert hasattr(tool_manager, 'setup_ffmpeg')
        assert callable(tool_manager.setup_ffmpeg)

    def test_has_setup_ytdlp_method(self, tool_manager):
        """测试setup_ytdlp方法存在"""
        assert hasattr(tool_manager, 'setup_ytdlp')
        assert callable(tool_manager.setup_ytdlp)

    def test_has_check_faster_whisper_method(self, tool_manager):
        """测试check_faster_whisper方法存在"""
        assert hasattr(tool_manager, 'check_faster_whisper')
        assert callable(tool_manager.check_faster_whisper)

    def test_has_install_faster_whisper_method(self, tool_manager):
        """测试install_faster_whisper方法存在"""
        assert hasattr(tool_manager, 'install_faster_whisper')
        assert callable(tool_manager.install_faster_whisper)


@pytest.mark.core
@pytest.mark.unit
class TestToolManagerProperties:
    """工具管理器属性测试"""

    @pytest.fixture
    def tool_manager(self):
        """创建工具管理器实例"""
        return ToolManager()

    def test_system_property(self, tool_manager):
        """测试system属性"""
        assert hasattr(tool_manager, 'system')
        assert isinstance(tool_manager.system, str)
        assert len(tool_manager.system) > 0

    def test_ffmpeg_path_property_type(self, tool_manager):
        """测试ffmpeg_path属性类型"""
        if tool_manager.ffmpeg_path is not None:
            assert isinstance(tool_manager.ffmpeg_path, Path)

    def test_ytdlp_path_property_type(self, tool_manager):
        """测试ytdlp_path属性类型"""
        if tool_manager.ytdlp_path is not None:
            assert isinstance(tool_manager.ytdlp_path, Path)
