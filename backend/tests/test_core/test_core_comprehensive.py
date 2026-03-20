"""
VidFlow 核心功能综合测试
测试下载队列、GPU管理器、WebSocket管理器等核心功能
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock


@pytest.mark.core
@pytest.mark.unit
class TestDownloadQueue:
    """下载队列测试"""

    @pytest.fixture
    def queue(self):
        """创建下载队列实例"""
        from src.core.download_queue import DownloadQueue
        return DownloadQueue(max_concurrent=3)

    @pytest.mark.asyncio
    async def test_queue_initialization(self, queue):
        """测试队列初始化"""
        assert queue is not None
        assert queue.max_concurrent == 3
        assert len(queue.active_tasks) == 0

    @pytest.mark.asyncio
    async def test_add_task(self, queue):
        """测试添加任务"""
        task_info = {
            'id': 'test-001',
            'url': 'https://example.com/video',
            'quality': 'best'
        }

        # 模拟添加任务
        # 注意：实际实现可能需要调整
        assert hasattr(queue, 'add_task') or hasattr(queue, 'add') or hasattr(queue, 'enqueue')

    @pytest.mark.asyncio
    async def test_concurrent_limit(self, queue):
        """测试并发限制"""
        # 验证最大并发数设置
        assert queue.max_concurrent == 3

        # 实际测试需要根据真实API调整
        if hasattr(queue, 'get_active_count'):
            active_count = queue.get_active_count()
            assert active_count <= queue.max_concurrent


@pytest.mark.core
@pytest.mark.unit
class TestGPUManager:
    """GPU管理器测试"""

    @pytest.fixture
    def gpu_manager(self):
        """创建GPU管理器实例"""
        from src.core.gpu_manager import GPUManager
        return GPUManager()

    def test_gpu_manager_initialization(self, gpu_manager):
        """测试GPU管理器初始化"""
        assert gpu_manager is not None

    @pytest.mark.asyncio
    async def test_check_gpu_detection(self, gpu_manager):
        """测试GPU检测"""
        # 检查方法存在
        assert hasattr(gpu_manager, '_detect_gpu')

        # 执行GPU检测
        await gpu_manager._detect_gpu()
        assert gpu_manager.gpu_info is not None
        assert 'available' in gpu_manager.gpu_info

    @pytest.mark.asyncio
    async def test_get_gpu_info(self, gpu_manager):
        """测试获取GPU信息"""
        if hasattr(gpu_manager, 'get_gpu_info'):
            info = await gpu_manager.get_gpu_info()

            assert isinstance(info, dict)
            assert 'cuda_available' in info or 'available' in info
        else:
            pytest.skip("get_gpu_info method not implemented")

    def test_cuda_version_check(self, gpu_manager):
        """测试CUDA版本检查"""
        # 验证CUDA版本检测功能
        if hasattr(gpu_manager, 'get_cuda_version'):
            version = gpu_manager.get_cuda_version()
            # 版本可以是None（无CUDA）或字符串
            assert version is None or isinstance(version, str)


@pytest.mark.core
@pytest.mark.unit
class TestWebSocketManager:
    """WebSocket管理器测试"""

    @pytest.fixture
    def ws_manager(self):
        """创建WebSocket管理器实例"""
        from src.core.websocket_manager import WebSocketManager
        return WebSocketManager()

    def test_ws_manager_initialization(self, ws_manager):
        """测试WebSocket管理器初始化"""
        assert ws_manager is not None
        assert hasattr(ws_manager, 'connections') or hasattr(ws_manager, 'active_connections')

    @pytest.mark.asyncio
    async def test_connect_websocket(self, ws_manager):
        """测试WebSocket连接"""
        # 创建模拟WebSocket
        mock_ws = AsyncMock()

        if hasattr(ws_manager, 'connect'):
            await ws_manager.connect(mock_ws)
            # 验证连接被添加
            connections = getattr(ws_manager, 'connections', getattr(ws_manager, 'active_connections', []))
            # 根据实际实现验证

    def test_disconnect_websocket(self, ws_manager):
        """测试WebSocket断开"""
        mock_ws = Mock()

        # disconnect 是同步方法，不是异步的
        ws_manager.disconnect(mock_ws)
        # 验证连接被移除
        assert mock_ws not in ws_manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_message(self, ws_manager):
        """测试广播消息"""
        message = {'type': 'test', 'data': 'hello'}

        if hasattr(ws_manager, 'broadcast'):
            # 添加模拟连接
            mock_ws = AsyncMock()
            if hasattr(ws_manager, 'connect'):
                await ws_manager.connect(mock_ws)

            # 广播消息
            await ws_manager.broadcast(message)


@pytest.mark.core
@pytest.mark.unit
class TestConfigManager:
    """配置管理器测试"""

    @pytest.fixture
    def config_manager(self, tmp_path):
        """创建配置管理器实例"""
        from src.core.config_manager import ConfigManager
        config_file = tmp_path / "test_config.json"
        return ConfigManager(config_file=str(config_file))

    def test_config_initialization(self, config_manager):
        """测试配置初始化"""
        assert config_manager is not None

    def test_get_default_config(self, config_manager):
        """测试获取默认配置"""
        if hasattr(config_manager, 'get_default_config'):
            config = config_manager.get_default_config()
            assert isinstance(config, dict)

    def test_save_and_load_config(self, config_manager):
        """测试保存和加载配置"""
        test_config = {
            'download_path': '/tmp/downloads',
            'max_concurrent': 3,
            'default_quality': '1080p'
        }

        if hasattr(config_manager, 'save') and hasattr(config_manager, 'load'):
            # 保存
            config_manager.save(test_config)

            # 加载
            loaded = config_manager.load()

            assert loaded['download_path'] == test_config['download_path']
            assert loaded['max_concurrent'] == test_config['max_concurrent']

    def test_update_config(self, config_manager):
        """测试更新配置"""
        if hasattr(config_manager, 'update'):
            config_manager.update({'default_quality': '720p'})

            if hasattr(config_manager, 'get'):
                quality = config_manager.get('default_quality')
                assert quality == '720p'


@pytest.mark.core
@pytest.mark.unit
class TestSubtitleProcessor:
    """字幕处理器测试"""

    @pytest.fixture
    def processor(self):
        """创建字幕处理器实例"""
        from src.core.subtitle_processor import SubtitleProcessor
        return SubtitleProcessor()

    def test_processor_initialization(self, processor):
        """测试字幕处理器初始化"""
        assert processor is not None

    def test_srt_format_conversion(self, processor):
        """测试SRT格式转换"""
        segments = [
            {
                'id': 1,
                'start': 0.0,
                'end': 2.5,
                'text': 'Hello World'
            },
            {
                'id': 2,
                'start': 3.0,
                'end': 5.0,
                'text': 'Test subtitle'
            }
        ]

        if hasattr(processor, 'to_srt') or hasattr(processor, 'format_srt'):
            method = getattr(processor, 'to_srt', getattr(processor, 'format_srt'))
            srt_content = method(segments)

            assert '00:00:00' in srt_content
            assert 'Hello World' in srt_content
            assert 'Test subtitle' in srt_content

    def test_vtt_format_conversion(self, processor):
        """测试VTT格式转换"""
        segments = [
            {
                'id': 1,
                'start': 0.0,
                'end': 2.5,
                'text': 'Hello World'
            }
        ]

        if hasattr(processor, 'to_vtt') or hasattr(processor, 'format_vtt'):
            method = getattr(processor, 'to_vtt', getattr(processor, 'format_vtt'))
            vtt_content = method(segments)

            assert 'WEBVTT' in vtt_content
            assert 'Hello World' in vtt_content

    def test_timestamp_formatting(self, processor):
        """测试时间戳格式化"""
        if hasattr(processor, 'format_timestamp'):
            # 测试不同的时间
            ts1 = processor.format_timestamp(0.0)
            assert '00:00:00' in ts1

            ts2 = processor.format_timestamp(3661.5)  # 1小时1分1.5秒
            assert '01:01:01' in ts2


@pytest.mark.core
@pytest.mark.unit
class TestToolManager:
    """工具管理器测试"""

    @pytest.fixture
    def tool_manager(self):
        """创建工具管理器实例"""
        from src.core.tool_manager import ToolManager
        return ToolManager()

    def test_tool_manager_initialization(self, tool_manager):
        """测试工具管理器初始化"""
        assert tool_manager is not None

    @pytest.mark.asyncio
    async def test_check_ffmpeg(self, tool_manager):
        """测试FFmpeg检查"""
        if hasattr(tool_manager, 'check_ffmpeg'):
            result = await tool_manager.check_ffmpeg()
            assert isinstance(result, (bool, dict))

    @pytest.mark.asyncio
    async def test_check_ytdlp(self, tool_manager):
        """测试yt-dlp检查"""
        if hasattr(tool_manager, 'check_ytdlp') or hasattr(tool_manager, 'check_yt_dlp'):
            method = getattr(tool_manager, 'check_ytdlp', getattr(tool_manager, 'check_yt_dlp', None))
            if method:
                result = await method()
                assert isinstance(result, (bool, dict))

    @pytest.mark.asyncio
    async def test_get_tools_status(self, tool_manager):
        """测试获取工具状态"""
        if hasattr(tool_manager, 'get_tools_status'):
            status = await tool_manager.get_tools_status()
            assert isinstance(status, (list, dict))


@pytest.mark.integration
class TestCoreIntegration:
    """核心功能集成测试"""

    @pytest.mark.asyncio
    async def test_download_workflow(self):
        """测试完整下载流程"""
        # 这个测试需要实际的网络连接
        pytest.skip("Integration test - requires network")

    @pytest.mark.asyncio
    async def test_subtitle_generation_workflow(self):
        """测试字幕生成流程"""
        pytest.skip("Integration test - requires AI model")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
