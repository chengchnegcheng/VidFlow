"""
微信视频号视频解密器

微信视频号使用 ISAAC64 流加密方案对视频前 128KB 进行加密。
解密需要从微信 API 响应中获取的 decodeKey (uint64 整数) 作为种子。

参考：
- github.com/nobiyou/wx_channel
- github.com/ltaoo/wx_channels_download
"""

import os
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Union

from .models import EncryptionType, DecryptResult
from .isaac64 import (
    Isaac64,
    generate_decryptor_array,
    decrypt_video_data,
    decrypt_video_file,
    ENCRYPTED_PREFIX_LENGTH,
)

logger = logging.getLogger(__name__)


class VideoDecryptor:
    """微信视频号视频解密器

    使用 ISAAC64 PRNG 生成伪随机字节流，与视频前 128KB 做 XOR 解密。
    需要从微信 API 获取 decodeKey (uint64) 作为种子。
    """

    def __init__(self):
        """初始化解密器"""
        pass

    @staticmethod
    def detect_encryption(file_path: Union[str, Path]) -> EncryptionType:
        """检测文件的加密类型

        Args:
            file_path: 文件路径

        Returns:
            加密类型
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return EncryptionType.UNKNOWN

        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)

                # 检查是否是有效的视频文件头
                if VideoDecryptor._is_valid_video_header(header):
                    return EncryptionType.NONE

                # 文件头不是有效视频格式，可能是 ISAAC64 加密
                file_size = file_path.stat().st_size
                if file_size > 1024:  # 大于 1KB 的文件才考虑加密
                    return EncryptionType.ISAAC64

        except Exception:
            return EncryptionType.UNKNOWN

        return EncryptionType.UNKNOWN

    @staticmethod
    def _is_valid_video_header(header: bytes) -> bool:
        """检查是否是有效的视频文件头

        Args:
            header: 文件头字节

        Returns:
            是否有效
        """
        if len(header) < 4:
            return False

        # MP4: 第 4-7 字节是 "ftyp"
        if len(header) >= 8 and header[4:8] == b'ftyp':
            return True

        # MP4: 以 free/skip/wide/mdat box 开始也是有效的
        if len(header) >= 8 and header[4:8] in [b'free', b'skip', b'wide', b'mdat', b'moov']:
            return True

        # WebM/MKV
        if header[:4] == b'\x1a\x45\xdf\xa3':
            return True

        # FLV
        if header[:3] == b'FLV':
            return True

        return False

    @staticmethod
    def parse_decode_key(key_str: str) -> Optional[int]:
        """解析 decodeKey 字符串为 uint64 整数

        微信视频号的 decodeKey 是一个十进制数字字符串（如 "2065249527"），
        作为 ISAAC64 PRNG 的种子。

        Args:
            key_str: decodeKey 字符串

        Returns:
            uint64 种子，解析失败返回 None
        """
        if not key_str:
            return None

        try:
            seed = int(key_str)
            if seed < 0:
                return None
            logger.info(f"解析 decodeKey: {key_str} -> seed={seed}")
            return seed
        except (ValueError, OverflowError):
            logger.warning(f"无法解析 decodeKey: {key_str}")
            return None

    @staticmethod
    async def decrypt(
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        decode_key: Optional[str] = None,
        encryption_type: Optional[EncryptionType] = None,
        progress_callback: Optional[callable] = None,
    ) -> DecryptResult:
        """解密视频文件

        使用 ISAAC64 算法解密微信视频号加密的视频。
        所有阻塞操作（文件IO、CPU密集型解密、ffmpeg subprocess）均在线程池中执行，
        避免阻塞 asyncio 事件循环。

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            decode_key: decodeKey 字符串（数字），ISAAC64 种子
            encryption_type: 加密类型（可选）
            progress_callback: 进度回调函数

        Returns:
            解密结果
        """
        return await asyncio.to_thread(
            VideoDecryptor._decrypt_sync,
            input_path, output_path, decode_key, encryption_type,
        )

    @staticmethod
    def _decrypt_sync(
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        decode_key: Optional[str] = None,
        encryption_type: Optional[EncryptionType] = None,
    ) -> DecryptResult:
        """解密视频文件（同步实现，在线程池中调用）"""
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            return DecryptResult(
                success=False,
                error_message=f"文件不存在: {input_path}",
            )

        try:
            with open(input_path, 'rb') as f:
                data = f.read()
        except Exception as e:
            return DecryptResult(
                success=False,
                error_message=f"读取文件失败: {e}",
            )

        if len(data) < 8:
            return DecryptResult(
                success=False,
                error_message="文件太小，无法解密",
            )

        # 检查是否已经是有效的视频
        if VideoDecryptor._is_valid_video_header(data[:16]):
            try:
                with open(output_path, 'wb') as f:
                    f.write(data)
                return DecryptResult(
                    success=True,
                    output_path=str(output_path),
                    encryption_type=EncryptionType.NONE,
                )
            except Exception as e:
                return DecryptResult(
                    success=False,
                    error_message=f"写入文件失败: {e}",
                )

        # 需要 decodeKey 才能解密
        if not decode_key:
            return DecryptResult(
                success=False,
                error_message="缺少 decodeKey，无法解密视频",
                encryption_type=EncryptionType.ISAAC64,
                additional_info={
                    'missing_key': True,
                    'suggestion': (
                        "需要从微信 API 获取 decodeKey 才能解密视频。\n"
                        "请确保嗅探器的 JS 注入脚本正常工作，\n"
                        "它会自动从微信页面提取 decodeKey。"
                    ),
                }
            )

        # 解析 decodeKey
        seed = VideoDecryptor.parse_decode_key(decode_key)
        if seed is None:
            return DecryptResult(
                success=False,
                error_message=f"无效的 decodeKey: {decode_key}",
                encryption_type=EncryptionType.ISAAC64,
            )

        # 使用 ISAAC64 解密
        logger.info(f"使用 ISAAC64 解密，seed={seed}，文件大小={len(data)} 字节")

        try:
            decrypted = bytearray(data)
            prefix_len = min(len(data), ENCRYPTED_PREFIX_LENGTH)
            decryptor_array = generate_decryptor_array(seed, prefix_len)

            # XOR 解密前 128KB
            for i in range(prefix_len):
                decrypted[i] ^= decryptor_array[i]

            logger.info(f"ISAAC64 解密完成，解密了 {prefix_len} 字节")
        except Exception as e:
            return DecryptResult(
                success=False,
                error_message=f"ISAAC64 解密失败: {e}",
                encryption_type=EncryptionType.ISAAC64,
            )

        # 验证解密结果
        if not VideoDecryptor._is_valid_video_header(bytes(decrypted[:16])):
            logger.warning(f"解密后文件头无效: {decrypted[:16].hex()}")
            return DecryptResult(
                success=False,
                error_message="解密后的文件头无效，decodeKey 可能不正确",
                encryption_type=EncryptionType.ISAAC64,
                additional_info={
                    'header_hex': decrypted[:16].hex(),
                    'suggestion': "decodeKey 可能不匹配此视频，请确认 decodeKey 来源正确。",
                }
            )

        # 写入解密后的文件
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(decrypted)
        except Exception as e:
            return DecryptResult(
                success=False,
                error_message=f"写入文件失败: {e}",
            )

        # 检查是否缺少 moov box，尝试 ffmpeg 修复
        repair_info = VideoDecryptor._try_ffmpeg_repair(output_path, decrypted)

        return DecryptResult(
            success=True,
            output_path=str(output_path),
            encryption_type=EncryptionType.ISAAC64,
            additional_info={'repair': repair_info} if repair_info else None,
        )

    @staticmethod
    def _try_ffmpeg_repair(output_path: Path, data: bytearray) -> Optional[dict]:
        """检查视频是否缺少 moov box，尝试 ffmpeg 修复

        Args:
            output_path: 输出文件路径
            data: 视频数据

        Returns:
            修复信息字典，不需要修复返回 None
        """
        search_range = min(1024 * 1024, len(data))
        has_moov = b'moov' in bytes(data[:search_range])
        if has_moov:
            return None

        logger.warning("视频文件缺少 moov box，尝试使用 ffmpeg 修复")
        repaired_path = output_path.with_suffix(output_path.suffix + '.repaired.mp4')

        ffmpeg_cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-i', str(output_path),
            '-c', 'copy', '-movflags', '+faststart',
            str(repaired_path),
        ]

        try:
            completed = subprocess.run(
                ffmpeg_cmd, capture_output=True, text=True, timeout=120,
            )
            if completed.returncode == 0 and repaired_path.exists() and repaired_path.stat().st_size > 0:
                output_path.unlink(missing_ok=True)
                repaired_path.rename(output_path)
                logger.info("ffmpeg 修复成功")
                return {'attempted': True, 'success': True, 'method': 'ffmpeg_faststart_remux'}

            return {
                'attempted': True, 'success': False,
                'method': 'ffmpeg_faststart_remux',
                'stderr': (completed.stderr or '').strip()[:2000],
            }
        except FileNotFoundError:
            return {'attempted': True, 'success': False, 'error': 'ffmpeg_not_found'}
        except subprocess.TimeoutExpired:
            return {'attempted': True, 'success': False, 'error': 'timeout'}
        except Exception as e:
            return {'attempted': True, 'success': False, 'error': str(e)}


# 兼容旧的函数式 API
def decrypt_video(input_path: str, output_path: Optional[str] = None, decode_key: Optional[str] = None) -> Tuple[bool, str]:
    """解密微信视频号视频（兼容旧 API）"""
    if output_path is None:
        output_path = str(Path(input_path).with_suffix('.decrypted.mp4'))

    result = asyncio.run(VideoDecryptor.decrypt(input_path, output_path, decode_key=decode_key))

    if result.success:
        return True, result.output_path
    else:
        return False, result.error_message
