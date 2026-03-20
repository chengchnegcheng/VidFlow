"""
微信视频号下载器

继承 BaseDownloader，实现视频号视频的下载功能。
支持从嗅探器获取的 URL 下载视频，并自动解密。
"""

import os
import asyncio
import inspect
import aiohttp
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from uuid import uuid4

from .base_downloader import BaseDownloader, _sanitize_filename
from ..channels.platform_detector import PlatformDetector
from ..channels.video_decryptor import VideoDecryptor
from ..channels.models import EncryptionType, ErrorCode, get_error_message


logger = logging.getLogger(__name__)


class ChannelsDownloader(BaseDownloader):
    """微信视频号下载器

    从嗅探器捕获的 URL 下载视频号视频，支持自动解密。
    """

    def __init__(self, output_dir: str = None, auto_decrypt: bool = True):
        """初始化下载器

        Args:
            output_dir: 输出目录
            auto_decrypt: 是否自动解密
        """
        super().__init__(output_dir, enable_cache=False)
        self.platform_name = "weixin_channels"
        self.auto_decrypt = auto_decrypt
        self._decryptor = VideoDecryptor()
        self._cancelled_tasks: set = set()

    @staticmethod
    def supports_url(url: str) -> bool:
        """检查是否支持该 URL

        Args:
            url: 视频 URL

        Returns:
            是否支持
        """
        return PlatformDetector.is_channels_video_url(url)

    @staticmethod
    def _normalize_video_url(url: str) -> str:
        """规范化视频号下载 URL（处理 fake-IP URL）。"""
        if not url:
            return url
        return PlatformDetector.normalize_channels_video_url(url)

    @staticmethod
    def _build_fallback_stem(url: str) -> str:
        """为视频号视频构建稳定的 ASCII 回退文件名词干。"""
        from urllib.parse import urlparse, parse_qs

        video_id = PlatformDetector.extract_video_id(url)
        if video_id:
            return f"channels_{video_id}"

        try:
            query_params = parse_qs(urlparse(url).query)
            for key in ("taskid", "taskId", "feedid", "feedId", "objectid", "objectId"):
                value = query_params.get(key, [None])[0]
                if not value:
                    continue
                short_value = str(value).split("-")[-1][:12]
                if short_value:
                    return f"channels_{short_value}"
        except Exception:
            logger.debug("Failed to build channels fallback stem", exc_info=True)

        return "channels_video"

    @staticmethod
    def _select_output_stem(url: str, title: Optional[str]) -> str:
        """优先使用经过清理的标题，回退到基于 ID 的稳定词干。"""
        if title:
            cleaned = _sanitize_filename(str(title).strip()).strip(" ._")
            if cleaned:
                return cleaned
        return ChannelsDownloader._build_fallback_stem(url)

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息

        由于视频号 URL 通常是直接的视频流地址，
        我们通过 HEAD 请求获取基本信息。

        Args:
            url: 视频 URL

        Returns:
            视频信息字典
        """
        if not url:
            return {"error": "URL 不能为空"}

        url = self._normalize_video_url(url)

        # 验证 URL 格式
        if not url.startswith(('http://', 'https://')):
            return {"error": f"无效的 URL 格式: {url}"}

        # 检查是否是占位符 URL
        from urllib.parse import urlparse
        import hashlib
        parsed = urlparse(url)
        if parsed.path in ('', '/') and not parsed.query:
            # 返回占位符信息而不是错误
            video_id = PlatformDetector.extract_video_id(url) or hashlib.md5(url.encode()).hexdigest()[:16]
            ip_suffix = parsed.hostname.split('.')[-1] if parsed.hostname else "unknown"

            return {
                "id": video_id,
                "title": f"channels_{ip_suffix}_waiting",
                "thumbnail": None,
                "duration": None,
                "resolution": None,
                "filesize": None,
                "url": url,
                "is_placeholder": True,
                "placeholder_message": "Please play this video in WeChat first to fetch complete metadata.",
            }

        try:
            logger.info(f"正在获取视频信息: {url[:100]}")

            # 使用微信 UA 和必要的请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI WindowsWechat/WMPF WindowsWechat(0x63090a13)',
                'Referer': 'https://channels.weixin.qq.com/',
            }

            async with aiohttp.ClientSession(headers=headers) as session:
                # 先尝试 HEAD 请求
                try:
                    async with session.head(url, allow_redirects=True, timeout=30) as response:
                        if response.status == 200:
                            response_headers = dict(response.headers)

                            # 提取元数据
                            metadata = PlatformDetector.extract_metadata_from_response(
                                url, response_headers, b""
                            )

                            # 提取视频 ID
                            video_id = PlatformDetector.extract_video_id(url)

                            return {
                                "id": video_id,
                                "title": metadata.title if metadata else self._build_fallback_stem(url),
                                "duration": metadata.duration if metadata else None,
                                "thumbnail": metadata.thumbnail if metadata else None,
                                "description": "",
                                "uploader": "WeChat Channels",
                                "filesize": metadata.filesize if metadata else None,
                                "resolution": metadata.resolution if metadata else None,
                                "url": url,
                                "formats": [{
                                    "format_id": "default",
                                    "ext": "mp4",
                                    "quality": metadata.resolution if metadata else "unknown",
                                    "filesize": metadata.filesize if metadata else 0,
                                }],
                            }
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    # HEAD 失败，尝试 GET 前几个字节
                    logger.info("HEAD 请求失败，尝试 GET 请求")
                    pass

                # 回退到 GET 请求（只获取前 1KB）
                async with session.get(url, allow_redirects=True, timeout=30) as response:
                    if response.status != 200:
                        return {"error": f"HTTP 错误: {response.status}，视频链接可能已过期"}

                    response_headers = dict(response.headers)

                    # 提取元数据
                    metadata = PlatformDetector.extract_metadata_from_response(
                        url, response_headers, b""
                    )

                    # 提取视频 ID
                    video_id = PlatformDetector.extract_video_id(url)

                    return {
                        "id": video_id,
                        "title": metadata.title if metadata else self._build_fallback_stem(url),
                        "duration": metadata.duration if metadata else None,
                        "thumbnail": metadata.thumbnail if metadata else None,
                        "description": "",
                        "uploader": "WeChat Channels",
                        "filesize": metadata.filesize if metadata else None,
                        "resolution": metadata.resolution if metadata else None,
                        "url": url,
                        "formats": [{
                            "format_id": "default",
                            "ext": "mp4",
                            "quality": metadata.resolution if metadata else "unknown",
                            "filesize": metadata.filesize if metadata else 0,
                        }],
                    }

        except asyncio.TimeoutError:
            logger.error(f"获取视频信息超时: {url[:100]}")
            return {"error": "Failed to fetch video metadata: request timed out."}
        except Exception as e:
            logger.exception(f"获取视频信息失败: {url[:100]}")
            return {"error": f"获取视频信息失败: {str(e)}"}

    async def download_video(
        self,
        url: str,
        quality: str = "best",
        output_path: Optional[str] = None,
        format_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None,
        auto_decrypt: Optional[bool] = None,
        decryption_key: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """下载视频

        Args:
            url: 视频 URL
            quality: 质量选择（视频号通常只有一个质量）
            output_path: 输出路径
            format_id: 格式 ID（未使用）
            progress_callback: 进度回调
            task_id: 任务 ID
            auto_decrypt: 是否自动解密（覆盖实例设置）
            decryption_key: 解密密钥（从视频信息中获取的 decodeKey）

        Returns:
            下载结果
        """
        if not url:
            return {
                "success": False,
                "error": "URL 不能为空",
                "error_code": "INVALID_URL",
            }

        url = self._normalize_video_url(url)

        # 确定是否自动解密
        should_decrypt = auto_decrypt if auto_decrypt is not None else self.auto_decrypt

        # 生成任务 ID
        if not task_id:
            task_id = f"channels_{uuid4().hex}"

        # 确定输出路径
        if output_path:
            output_file = Path(output_path)
        else:
            filename = f"{self._select_output_stem(url, title)}.mp4"
            output_file = self.output_dir / filename

        # 确保输出目录存在
        await asyncio.to_thread(output_file.parent.mkdir, parents=True, exist_ok=True)

        # 临时文件路径（用于加密视频）
        temp_file = output_file.with_suffix(".tmp")

        try:
            # 下载视频
            download_result = await self._download_file(
                url=url,
                output_path=temp_file,
                progress_callback=progress_callback,
                task_id=task_id,
            )

            if not download_result["success"]:
                return download_result

            # 检查是否被取消
            if task_id in self._cancelled_tasks:
                await self._cleanup_file_async(temp_file)
                self._cancelled_tasks.discard(task_id)
                return {
                    "success": False,
                    "error": get_error_message(ErrorCode.DOWNLOAD_CANCELLED),
                    "error_code": ErrorCode.DOWNLOAD_CANCELLED,
                }

            # 检测加密类型（同步文件IO，卸载到线程池）
            encryption_type = await asyncio.to_thread(VideoDecryptor.detect_encryption, temp_file)
            decrypted = False
            repair_info = None
            decode_key: Optional[str] = None
            if decryption_key is not None:
                candidate_key = str(decryption_key).strip()
                if candidate_key.isdigit():
                    decode_key = candidate_key

            # 加密的视频号载荷不可直接播放。
            # 仅在文件未加密或解密成功时写入 .mp4。
            if encryption_type != EncryptionType.NONE and should_decrypt and decode_key:
                # 使用 decryption_key 作为 ISAAC64 的 decodeKey
                logger.info(f"使用 decodeKey 进行 ISAAC64 解密: {decode_key}")

                # 更新进度：解密中
                if progress_callback:
                    await self._call_progress(progress_callback, {
                        "status": "decrypting",
                        "progress": 0,
                        "task_id": task_id,
                    })

                # 解密（使用 ISAAC64）
                decrypt_result = await VideoDecryptor.decrypt(
                    input_path=temp_file,
                    output_path=output_file,
                    decode_key=decode_key,
                    encryption_type=encryption_type,
                )

                if not decrypt_result.success:
                    # 解密失败，保留原始加密文件
                    logger.warning(f"Decrypt failed: {decrypt_result.error_message}. Keeping original encrypted file.")

                    # 构建详细的错误提示
                    error_message = decrypt_result.error_message
                    hint_message = None
                    repair_info = None

                    if decrypt_result.additional_info:
                        repair_info = decrypt_result.additional_info.get('repair')

                    # 检查是否是缺少 moov box 的情况
                    if decrypt_result.additional_info and decrypt_result.additional_info.get("missing_moov"):
                        hint_message = decrypt_result.additional_info.get("suggestion")
                    elif decrypt_result.additional_info and decrypt_result.additional_info.get("missing_key"):
                        hint_message = decrypt_result.additional_info.get("suggestion")
                    else:
                        hint_message = (
                            "Video decryption failed. Possible reasons:\n"
                            "1. decodeKey does not match this video\n"
                            "2. decodeKey is missing (requires JS injection script extraction)\n"
                            "3. Video URL has expired; please replay in WeChat and capture again"
                        )

                    if await asyncio.to_thread(temp_file.exists):
                        # 重命名为 .encrypted 扩展名，让用户知道这是加密文件
                        encrypted_file = output_file.with_suffix('.mp4.encrypted')
                        await asyncio.to_thread(temp_file.rename, encrypted_file)

                        enc_size = await asyncio.to_thread(lambda: encrypted_file.stat().st_size if encrypted_file.exists() else 0)
                        return {
                            "success": True,  # 下载成功，只是解密失败
                            "file_path": str(encrypted_file),
                            "file_size": enc_size,
                            "task_id": task_id,
                            "decrypted": False,
                            "encrypted": True,
                            "decrypt_error": error_message,
                            "decrypt_hint": hint_message,
                            "repair": repair_info,
                        }

                    out_size = await asyncio.to_thread(lambda: output_file.stat().st_size if output_file.exists() else 0)
                    return {
                        "success": True,  # 下载成功，只是解密失败
                        "file_path": str(output_file),
                        "file_size": out_size,
                        "task_id": task_id,
                        "decrypted": False,
                        "encrypted": True,
                        "decrypt_error": error_message,
                        "decrypt_hint": hint_message,
                        "repair": repair_info,
                    }

                # 解密成功，删除临时文件
                await self._cleanup_file_async(temp_file)
                decrypted = True

                # 返回修复信息（如果有）
                if decrypt_result.additional_info and decrypt_result.additional_info.get('repair'):
                    repair_info = decrypt_result.additional_info.get('repair')
            else:
                if encryption_type != EncryptionType.NONE:
                    encrypted_file = output_file.with_suffix(".mp4.encrypted")
                    logger.info(
                        "Keeping encrypted channels payload: decrypt=%s decode_key=%s",
                        should_decrypt,
                        "present" if decode_key else "missing",
                    )
                    if await asyncio.to_thread(temp_file.exists):
                        if await asyncio.to_thread(encrypted_file.exists):
                            await asyncio.to_thread(encrypted_file.unlink)
                        await asyncio.to_thread(temp_file.rename, encrypted_file)

                    hint_message = (
                        "Video payload is still encrypted. Replay the video and capture a valid decodeKey before downloading again."
                        if should_decrypt
                        else "Video payload is encrypted. Enable auto-decrypt with a valid decodeKey to produce a playable MP4."
                    )
                    enc_size2 = await asyncio.to_thread(lambda: encrypted_file.stat().st_size if encrypted_file.exists() else 0)
                    return {
                        "success": True,
                        "file_path": str(encrypted_file),
                        "file_size": enc_size2,
                        "task_id": task_id,
                        "decrypted": False,
                        "encrypted": True,
                        "decrypt_error": "Missing decodeKey" if should_decrypt and not decode_key else None,
                        "decrypt_hint": hint_message,
                        "repair": repair_info,
                    }

                # 不需要解密，直接重命名
                if await asyncio.to_thread(temp_file.exists):
                    # 检查目标文件是否存在，如果存在则删除
                    if await asyncio.to_thread(output_file.exists):
                        await asyncio.to_thread(output_file.unlink)
                    await asyncio.to_thread(temp_file.rename, output_file)

            # 获取文件大小
            file_size = await asyncio.to_thread(lambda: output_file.stat().st_size if output_file.exists() else 0)

            return {
                "success": True,
                "file_path": str(output_file),
                "file_size": file_size,
                "task_id": task_id,
                "decrypted": decrypted,
                "repair": repair_info,
            }

        except asyncio.CancelledError:
            await self._cleanup_file_async(temp_file)
            await self._cleanup_file_async(output_file)
            return {
                "success": False,
                "error": get_error_message(ErrorCode.DOWNLOAD_CANCELLED),
                "error_code": ErrorCode.DOWNLOAD_CANCELLED,
            }
        except Exception as e:
            logger.exception("Download failed")
            await self._cleanup_file_async(temp_file)
            return {
                "success": False,
                "error": f"下载失败: {str(e)}",
            }

    async def _download_file(
        self,
        url: str,
        output_path: Path,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """下载文件

        Args:
            url: 文件 URL
            output_path: 输出路径
            progress_callback: 进度回调
            task_id: 任务 ID

        Returns:
            下载结果
        """
        try:
            timeout = aiohttp.ClientTimeout(total=3600, connect=30)

            # 使用微信 UA 和必要的请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI WindowsWechat/WMPF WindowsWechat(0x63090a13)',
                'Referer': 'https://channels.weixin.qq.com/',
            }

            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_msg = f"HTTP 错误: {response.status}"
                        if response.status == 403:
                            error_msg += "，视频链接可能已过期，请重新在微信中播放视频"
                        elif response.status == 404:
                            error_msg += ", video not found or removed."
                        return {
                            "success": False,
                            "error": error_msg,
                            "error_code": ErrorCode.NETWORK_ERROR if response.status != 403 else ErrorCode.VIDEO_EXPIRED,
                        }

                    total_size = int(response.headers.get("Content-Length", 0))
                    downloaded = 0

                    f = open(output_path, "wb")
                    try:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            # 检查是否被取消
                            if task_id and task_id in self._cancelled_tasks:
                                f.close()
                                return {
                                    "success": False,
                                    "error": get_error_message(ErrorCode.DOWNLOAD_CANCELLED),
                                    "error_code": ErrorCode.DOWNLOAD_CANCELLED,
                                }

                            await asyncio.to_thread(f.write, chunk)
                            downloaded += len(chunk)

                            # 更新进度
                            if progress_callback:
                                progress = int(downloaded / total_size * 100) if total_size > 0 else 0
                                speed = 0  # TODO: 计算速度
                                await self._call_progress(progress_callback, {
                                    "status": "downloading",
                                    "progress": progress,
                                    "downloaded": downloaded,
                                    "total": total_size,
                                    "speed": speed,
                                    "task_id": task_id,
                                })
                    finally:
                        f.close()

                    return {
                        "success": True,
                        "file_path": str(output_path),
                        "file_size": downloaded,
                    }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "下载超时",
                "error_code": ErrorCode.NETWORK_ERROR,
            }
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error": f"网络错误: {str(e)}",
                "error_code": ErrorCode.NETWORK_ERROR,
            }

    async def _call_progress(self, callback: Callable, data: Dict[str, Any]) -> None:
        """调用进度回调

        Args:
            callback: 回调函数
            data: 进度数据
        """
        try:
            if inspect.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception:
            logger.exception("Progress callback error")

    def cancel_download(self, task_id: str) -> bool:
        """取消下载

        Args:
            task_id: 任务 ID

        Returns:
            是否成功标记取消
        """
        self._cancelled_tasks.add(task_id)
        return True

    def _cleanup_file(self, file_path: Path) -> None:
        """清理文件（同步版本，供非 async 上下文使用）

        Args:
            file_path: 文件路径
        """
        try:
            if file_path and file_path.exists():
                file_path.unlink()
        except Exception:
            logger.exception(f"Failed to cleanup file: {file_path}")

    async def _cleanup_file_async(self, file_path: Path) -> None:
        """清理文件（异步版本，避免阻塞事件循环）"""
        try:
            await asyncio.to_thread(self._cleanup_file, file_path)
        except Exception:
            pass
