"""
视频号下载器属性测试

Property 6: Download Produces Valid Output
Property 7: Download Cancellation Cleanup
Property 12: Progress Callbacks Contain Valid Data
Validates: Requirements 4.1, 4.4, 4.6, 4.2
"""

import pytest
from hypothesis import given, strategies as st, settings
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import aiohttp

from src.core.downloaders.channels_downloader import ChannelsDownloader
from src.core.channels.models import EncryptionType


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    """创建临时目录"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def downloader(temp_dir):
    """创建下载器实例"""
    return ChannelsDownloader(output_dir=str(temp_dir))


# ============================================================================
# Property 6: Download Produces Valid Output
# Validates: Requirements 4.1, 4.4
# ============================================================================

class TestDownloadProducesValidOutput:
    """
    Property 6: Download Produces Valid Output

    For any valid video URL, a successful download should produce a file
    at the specified output path with non-zero size. The returned result
    should contain the correct file path.

    **Feature: weixin-channels-download, Property 6: Download Produces Valid Output**
    **Validates: Requirements 4.1, 4.4**
    """

    def test_supports_channels_url(self):
        """应该支持视频号 URL"""
        assert ChannelsDownloader.supports_url("https://finder.video.qq.com/video.mp4") is True
        assert ChannelsDownloader.supports_url("https://channels.weixin.qq.com/video.mp4") is True

    def test_does_not_support_other_urls(self):
        """不应该支持其他 URL"""
        assert ChannelsDownloader.supports_url("https://www.youtube.com/watch?v=123") is False
        assert ChannelsDownloader.supports_url("https://www.bilibili.com/video/BV123") is False

    @pytest.mark.asyncio
    async def test_download_empty_url_fails(self, downloader):
        """空 URL 下载应该失败"""
        result = await downloader.download_video("")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_download_with_mock_response(self, downloader, temp_dir):
        """使用 mock 响应测试下载"""
        # 创建 mock 视频数据
        video_data = b'\x00\x00\x00\x1c\x66\x74\x79\x70' + b'\x00' * 1000

        # Mock aiohttp
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": str(len(video_data))}

        async def mock_iter_chunked(size):
            yield video_data

        mock_response.content.iter_chunked = mock_iter_chunked
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await downloader.download_video(
                "https://finder.video.qq.com/video.mp4",
                output_path=str(temp_dir / "test.mp4")
            )

        assert result["success"] is True
        assert "file_path" in result
        assert Path(result["file_path"]).exists()

    @pytest.mark.asyncio
    async def test_get_video_info_empty_url(self, downloader):
        """空 URL 获取信息应该返回错误"""
        result = await downloader.get_video_info("")
        assert "error" in result


# ============================================================================
# Property 7: Download Cancellation Cleanup
# Validates: Requirements 4.6
# ============================================================================

class TestDownloadCancellationCleanup:
    """
    Property 7: Download Cancellation Cleanup

    For any in-progress download that is cancelled, the partial file should
    be removed and the download should stop. No orphaned temporary files
    should remain.

    **Feature: weixin-channels-download, Property 7: Download Cancellation Cleanup**
    **Validates: Requirements 4.6**
    """

    def test_cancel_download_marks_task(self, downloader):
        """取消下载应该标记任务"""
        task_id = "test-task-123"

        result = downloader.cancel_download(task_id)

        assert result is True
        assert task_id in downloader._cancelled_tasks

    @pytest.mark.asyncio
    async def test_cancelled_download_returns_cancelled_error(self, downloader, temp_dir):
        """取消的下载应该返回取消错误"""
        task_id = "test-cancel-task"

        # 预先标记取消
        downloader.cancel_download(task_id)

        # 创建 mock 响应
        video_data = b'\x00' * 1000

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": str(len(video_data))}

        async def mock_iter_chunked(size):
            yield video_data

        mock_response.content.iter_chunked = mock_iter_chunked
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await downloader.download_video(
                "https://finder.video.qq.com/video.mp4",
                task_id=task_id
            )

        assert result["success"] is False
        assert result.get("error_code") == "DOWNLOAD_CANCELLED"

    def test_cleanup_file_removes_existing_file(self, downloader, temp_dir):
        """清理应该删除存在的文件"""
        test_file = temp_dir / "test.tmp"
        test_file.write_bytes(b"test data")

        assert test_file.exists()

        downloader._cleanup_file(test_file)

        assert not test_file.exists()

    def test_cleanup_file_handles_nonexistent_file(self, downloader, temp_dir):
        """清理不存在的文件不应该报错"""
        nonexistent = temp_dir / "nonexistent.tmp"

        # 不应该抛出异常
        downloader._cleanup_file(nonexistent)


# ============================================================================
# Property 12: Progress Callbacks Contain Valid Data
# Validates: Requirements 4.2
# ============================================================================

class TestProgressCallbacksContainValidData:
    """
    Property 12: Progress Callbacks Contain Valid Data

    For any download or decryption operation with a progress callback,
    the callback should be invoked with valid progress data: percentage
    should be between 0 and 100, speed should be non-negative, and ETA
    should be non-negative or None.

    **Feature: weixin-channels-download, Property 12: Progress Callbacks Contain Valid Data**
    **Validates: Requirements 4.2**
    """

    @pytest.mark.asyncio
    async def test_progress_callback_receives_valid_data(self, downloader, temp_dir):
        """进度回调应该接收有效数据"""
        progress_data_list = []

        async def progress_callback(data):
            progress_data_list.append(data)

        # 创建 mock 响应
        video_data = b'\x00\x00\x00\x1c\x66\x74\x79\x70' + b'\x00' * 1000

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": str(len(video_data))}

        async def mock_iter_chunked(size):
            yield video_data

        mock_response.content.iter_chunked = mock_iter_chunked
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            await downloader.download_video(
                "https://finder.video.qq.com/video.mp4",
                output_path=str(temp_dir / "test.mp4"),
                progress_callback=progress_callback
            )

        # 验证进度数据
        assert len(progress_data_list) > 0

        for data in progress_data_list:
            assert "status" in data
            assert "progress" in data
            assert 0 <= data["progress"] <= 100

    @pytest.mark.asyncio
    async def test_progress_callback_error_does_not_break_download(self, downloader, temp_dir):
        """进度回调错误不应该中断下载"""
        def bad_callback(data):
            raise Exception("Callback error")

        # 创建 mock 响应
        video_data = b'\x00\x00\x00\x1c\x66\x74\x79\x70' + b'\x00' * 100

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": str(len(video_data))}

        async def mock_iter_chunked(size):
            yield video_data

        mock_response.content.iter_chunked = mock_iter_chunked
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await downloader.download_video(
                "https://finder.video.qq.com/video.mp4",
                output_path=str(temp_dir / "test.mp4"),
                progress_callback=bad_callback
            )

        # 下载应该仍然成功
        assert result["success"] is True


# ============================================================================
# Additional Unit Tests
# ============================================================================

class TestChannelsDownloaderUnit:
    """下载器单元测试"""

    def test_platform_name(self, downloader):
        """平台名称应该正确"""
        assert downloader.platform_name == "weixin_channels"

    def test_auto_decrypt_default(self, temp_dir):
        """默认应该启用自动解密"""
        downloader = ChannelsDownloader(output_dir=str(temp_dir))
        assert downloader.auto_decrypt is True

    def test_auto_decrypt_disabled(self, temp_dir):
        """可以禁用自动解密"""
        downloader = ChannelsDownloader(output_dir=str(temp_dir), auto_decrypt=False)
        assert downloader.auto_decrypt is False

    def test_output_dir_created(self, temp_dir):
        """输出目录应该被创建"""
        output_dir = temp_dir / "new_dir"
        downloader = ChannelsDownloader(output_dir=str(output_dir))

        assert output_dir.exists()

    @pytest.mark.asyncio
    async def test_download_network_error(self, downloader):
        """网络错误应该返回错误结果"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Network error"))
            mock_session_class.return_value = mock_session

            result = await downloader._download_file(
                "https://finder.video.qq.com/video.mp4",
                Path("/tmp/test.mp4")
            )

        assert result["success"] is False
        assert "error" in result
