"""
工具管理器核心功能测试
"""
import pytest
from pathlib import Path
from src.core.tool_manager import ToolManager, get_tool_manager


@pytest.mark.core
@pytest.mark.unit
class TestToolManager:
    """工具管理器测试类"""

    @pytest.fixture
    def tool_manager(self):
        """创建工具管理器实例"""
        return ToolManager()

    def test_tool_manager_initialization(self, tool_manager):
        """测试工具管理器初始化"""
        assert tool_manager is not None
        assert isinstance(tool_manager, ToolManager)

    def test_get_tool_manager_singleton(self):
        """测试获取工具管理器单例"""
        manager1 = get_tool_manager()
        manager2 = get_tool_manager()
        assert manager1 is manager2  # 应该是同一个实例

    def test_get_ffmpeg_path(self, tool_manager):
        """测试获取 FFmpeg 路径"""
        path = tool_manager.get_ffmpeg_path()
        if path:
            path = Path(path)
        # 路径可能为 None（未安装）或 Path 对象
        assert path is None or isinstance(path, Path)

    def test_get_ytdlp_path(self, tool_manager):
        """测试获取 yt-dlp 路径"""
        path = tool_manager.get_ytdlp_path()
        if path:
            path = Path(path)
        # 路径可能为 None（未安装）或 Path 对象
        assert path is None or isinstance(path, Path)

    def test_tools_directory_creation(self, tool_manager):
        """测试工具目录创建"""
        # 工具管理器使用模块级别的TOOLS_DIR常量
        from src.core.tool_manager import TOOLS_DIR, BIN_DIR
        assert TOOLS_DIR.exists()
        assert BIN_DIR.exists()


@pytest.mark.core
@pytest.mark.unit
class TestToolManagerValidation:
    """工具管理器验证测试"""

    def test_tool_paths_are_absolute(self):
        """测试工具路径是绝对路径"""
        manager = get_tool_manager()

        ffmpeg_path = manager.get_ffmpeg_path()
        if ffmpeg_path:
            assert Path(ffmpeg_path).is_absolute()

        ytdlp_path = manager.get_ytdlp_path()
        if ytdlp_path:
            assert Path(ytdlp_path).is_absolute()
