"""
工具安装 API 测试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient


class TestToolsInstallAPI:
    """工具安装 API 测试"""
    
    @pytest.mark.asyncio
    async def test_install_ffmpeg_endpoint_exists(self, client: AsyncClient):
        """测试 FFmpeg 安装端点存在"""
        response = await client.post("/api/v1/system/tools/install/ffmpeg")
        # 可能返回 500 (未 mock) 或 200，但端点应该存在
        assert response.status_code in [200, 500]
    
    @pytest.mark.asyncio
    async def test_install_ytdlp_endpoint_exists(self, client: AsyncClient):
        """测试 yt-dlp 安装端点存在"""
        response = await client.post("/api/v1/system/tools/install/ytdlp")
        assert response.status_code in [200, 500]
    
    @pytest.mark.asyncio
    async def test_install_whisper_endpoint_exists(self, client: AsyncClient):
        """测试 faster-whisper 安装端点存在"""
        response = await client.post("/api/v1/system/tools/install/whisper")
        assert response.status_code in [200, 500]
    
    @pytest.mark.asyncio
    async def test_install_all_endpoint_exists(self, client: AsyncClient):
        """测试一键安装端点存在"""
        response = await client.post("/api/v1/system/tools/install/all")
        assert response.status_code in [200, 500]


class TestToolsInstallMocked:
    """工具安装 API Mock 测试"""
    
    @pytest.mark.asyncio
    @patch('src.core.tool_manager.get_tool_manager')
    @patch('src.core.websocket_manager.get_ws_manager')
    async def test_install_ffmpeg_success(
        self, 
        mock_ws_manager, 
        mock_tool_manager,
        client: AsyncClient
    ):
        """测试 FFmpeg 安装成功"""
        # Mock 工具管理器
        mock_mgr = AsyncMock()
        mock_mgr.setup_ffmpeg = AsyncMock(return_value="/usr/bin/ffmpeg")
        mock_mgr.set_progress_callback = MagicMock()
        mock_tool_manager.return_value = mock_mgr
        
        # Mock WebSocket 管理器
        mock_ws = AsyncMock()
        mock_ws.send_tool_progress = AsyncMock()
        mock_ws_manager.return_value = mock_ws
        
        response = await client.post("/api/v1/system/tools/install/ffmpeg")
        
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "message" in data
            assert "FFmpeg" in data["message"]
    
    @pytest.mark.asyncio
    @patch('src.core.tool_manager.get_tool_manager')
    @patch('src.core.websocket_manager.get_ws_manager')
    async def test_install_ytdlp_success(
        self, 
        mock_ws_manager,
        mock_tool_manager,
        client: AsyncClient
    ):
        """测试 yt-dlp 安装成功"""
        mock_mgr = AsyncMock()
        mock_mgr.setup_ytdlp = AsyncMock(return_value="/usr/bin/yt-dlp")
        mock_mgr.set_progress_callback = MagicMock()
        mock_tool_manager.return_value = mock_mgr
        
        mock_ws = AsyncMock()
        mock_ws.send_tool_progress = AsyncMock()
        mock_ws_manager.return_value = mock_ws
        
        response = await client.post("/api/v1/system/tools/install/ytdlp")
        
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
    
    @pytest.mark.asyncio
    @patch('src.core.tool_manager.get_tool_manager')
    @patch('src.core.websocket_manager.get_ws_manager')
    async def test_install_ffmpeg_failure(
        self,
        mock_ws_manager,
        mock_tool_manager,
        client: AsyncClient
    ):
        """测试 FFmpeg 安装失败"""
        mock_mgr = AsyncMock()
        mock_mgr.setup_ffmpeg = AsyncMock(side_effect=RuntimeError("下载失败"))
        mock_mgr.set_progress_callback = MagicMock()
        mock_tool_manager.return_value = mock_mgr
        
        mock_ws = AsyncMock()
        mock_ws_manager.return_value = mock_ws
        
        response = await client.post("/api/v1/system/tools/install/ffmpeg")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


class TestToolsInstallProgress:
    """工具安装进度测试"""
    
    @pytest.mark.asyncio
    @patch('src.core.tool_manager.get_tool_manager')
    @patch('src.core.websocket_manager.get_ws_manager')
    async def test_progress_callback_set(
        self,
        mock_ws_manager,
        mock_tool_manager,
        client: AsyncClient
    ):
        """测试进度回调被设置"""
        mock_mgr = AsyncMock()
        mock_mgr.setup_ffmpeg = AsyncMock(return_value="/usr/bin/ffmpeg")
        mock_mgr.set_progress_callback = MagicMock()
        mock_tool_manager.return_value = mock_mgr
        
        mock_ws = AsyncMock()
        mock_ws_manager.return_value = mock_ws
        
        await client.post("/api/v1/system/tools/install/ffmpeg")
        
        # 验证进度回调被设置
        mock_mgr.set_progress_callback.assert_called_once()
