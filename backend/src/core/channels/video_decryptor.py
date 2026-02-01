"""
微信视频号视频解密器

微信视频号下载的视频可能被加密。
经过分析发现，文件前面约 498KB 是加密的头部，后面是有效的 MP4 数据（以 free box 开始）。
"""

import os
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.parse import urlparse, parse_qs

from .models import EncryptionType, DecryptResult

logger = logging.getLogger(__name__)

# 加密区域大小（微信视频号特有）
# 根据 KingsleyYau/WeChatChannelsDownloader 项目：前 0x20000 字节被加密
ENCRYPTED_HEADER_SIZE = 0x20000  # 131,072 字节 = 128KB

# 视频文件魔数
VIDEO_MAGIC_NUMBERS = {
    b'\x00\x00\x00': 'mp4',  # MP4 (ftyp box)
    b'\x1a\x45\xdf\xa3': 'webm',  # WebM/MKV
    b'FLV': 'flv',  # FLV
    b'\x00\x00\x01': 'ts',  # MPEG-TS
}


class VideoDecryptor:
    """微信视频号视频解密器
    
    支持检测加密类型、解密视频文件。
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
                
                # 微信视频号特殊处理：搜索 MP4 box 标记
                f.seek(0)
                data = f.read(min(600000, file_path.stat().st_size))  # 读取前 600KB
                
                # 搜索 free 或 mdat box
                for marker in [b'free', b'mdat', b'moov']:
                    pos = data.find(marker)
                    if pos > 4 and pos < 550000:  # 在合理范围内找到
                        # 检查是否是有效的 box（前4字节是大小）
                        try:
                            import struct
                            box_size = struct.unpack('>I', data[pos-4:pos])[0]
                            if 8 <= box_size <= len(data):
                                logger.info(f"检测到微信视频号加密：在位置 {pos-4} 找到 {marker.decode()} box")
                                return EncryptionType.XOR  # 使用 XOR 类型表示需要提取
                        except:
                            pass
                
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
        
        # WebM/MKV
        if header[:4] == b'\x1a\x45\xdf\xa3':
            return True
        
        # FLV
        if header[:3] == b'FLV':
            return True
        
        # MPEG-TS（需要更严格的验证，避免误判）
        # TS 文件每 188 字节一个包，每个包都以 0x47 开头
        if header[0] == 0x47 and len(header) >= 188:
            # 检查第二个包是否也以 0x47 开头
            if header[188] == 0x47:
                return True
        
        return False
    
    @staticmethod
    def encrypt_xor(data: bytes, key: bytes) -> bytes:
        """XOR 加密/解密
        
        Args:
            data: 数据
            key: 密钥
            
        Returns:
            加密/解密后的数据
        """
        if not key:
            return data
        
        result = bytearray(len(data))
        key_len = len(key)
        
        for i, b in enumerate(data):
            result[i] = b ^ key[i % key_len]
        
        return bytes(result)
    
    @staticmethod
    def parse_key(key_str: str) -> Optional[bytes]:
        """解析密钥字符串为字节
        
        微信视频号的 decodeKey 是一个数字字符串（如 "2065249527"），
        根据逆向分析，需要转换为 4 字节小端序。
        
        对于 encfilekey（从 URL 获取的长字符串），使用 MD5 哈希生成密钥。
        
        Args:
            key_str: 密钥字符串
            
        Returns:
            解密密钥字节，如果解析失败则返回 None
        """
        if not key_str:
            return None
        
        try:
            import struct
            import hashlib
            
            # 判断密钥类型
            if len(key_str) < 20:
                # 短密钥，当作 decodeKey（数字）
                try:
                    key_int = int(key_str)
                    # 方法 1: 4 字节小端序（最可能的方式）
                    key_bytes = struct.pack('<I', key_int)
                    logger.info(f"解析 decodeKey: {key_str} -> {key_bytes.hex()}")
                    return key_bytes
                except ValueError:
                    pass
            else:
                # 长密钥，当作 encfilekey
                # 使用 MD5 哈希生成固定长度的密钥
                key_hash = hashlib.md5(key_str.encode()).digest()
                # 取前 4 字节作为 XOR 密钥
                key_bytes = key_hash[:4]
                logger.info(f"解析 encfilekey: {key_str[:50]}... -> {key_bytes.hex()}")
                return key_bytes
            
            # 尝试解析为十六进制
            try:
                return bytes.fromhex(key_str)
            except ValueError:
                # 作为字符串处理
                return key_str.encode()
                
        except Exception as e:
            logger.exception(f"解析密钥失败: {e}")
            return None
    
    @staticmethod
    def extract_key_from_url(url: str) -> Optional[bytes]:
        """从 URL 中提取解密密钥
        
        Args:
            url: 视频 URL
            
        Returns:
            解密密钥，如果没有则返回 None
        """
        if not url:
            return None
        
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            # 优先查找 encfilekey（视频号专用）
            if 'encfilekey' in params:
                encfilekey = params['encfilekey'][0]
                logger.info(f"从 URL 提取到 encfilekey: {encfilekey[:50]}...")
                return VideoDecryptor.parse_key(encfilekey)
            
            # 其他常见的密钥参数名
            key_params = ['key', 'decryptkey', 'decodekey', 'k']
            
            for param in key_params:
                if param in params:
                    key_str = params[param][0]
                    logger.info(f"从 URL 提取到 {param}: {key_str}")
                    return VideoDecryptor.parse_key(key_str)
            
            logger.warning("URL 中未找到解密密钥参数")
            return None
        except Exception as e:
            logger.exception(f"从 URL 提取密钥失败: {e}")
            return None
    
    @staticmethod
    async def decrypt(
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        key: Optional[bytes] = None,
        encryption_type: Optional[EncryptionType] = None,
        progress_callback: Optional[callable] = None,
    ) -> DecryptResult:
        """解密视频文件
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            key: 解密密钥，如果为 None 则自动检测
            encryption_type: 加密类型（可选，用于优化检测）
            progress_callback: 进度回调函数
            
        Returns:
            解密结果
        """
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
            
            # 报告读取完成
            if progress_callback:
                try:
                    if asyncio.iscoroutinefunction(progress_callback):
                        # 如果是异步函数，需要在事件循环中调用
                        pass  # 暂时跳过，因为这里不在 async 上下文中
                    else:
                        progress_callback(1, 3)  # 读取完成 (1/3)
                except Exception:
                    pass
                
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
            # 直接复制
            try:
                with open(output_path, 'wb') as f:
                    f.write(data)
                
                # 报告完成
                if progress_callback:
                    try:
                        if asyncio.iscoroutinefunction(progress_callback):
                            pass  # 暂时跳过
                        else:
                            progress_callback(3, 3)  # 完成 (3/3)
                    except Exception:
                        pass
                    
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
        
        # 尝试解密/提取
        decrypted = None
        detected_key = None
        
        # 报告解密开始
        if progress_callback:
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    pass  # 暂时跳过
                else:
                    progress_callback(2, 3)  # 解密中 (2/3)
            except Exception:
                pass
        
        # 方法 1: 如果提供了密钥，使用 XOR 解密前 0x20000 字节
        if key:
            logger.info(f"使用提供的密钥进行 XOR 解密（密钥长度: {len(key)} 字节）")
            decrypt_size = min(ENCRYPTED_HEADER_SIZE, len(data))
            decrypted = bytearray(data)
            key_len = len(key)
            
            # XOR 解密前 0x20000 字节
            for i in range(decrypt_size):
                decrypted[i] ^= key[i % key_len]
            
            detected_key = key
            logger.info(f"XOR 解密完成，解密了 {decrypt_size} 字节")
        else:
            # 方法 2: 没有密钥时，尝试从加密数据中提取 MP4
            import struct
            mp4_extracted = False
            
            logger.info("未提供密钥，尝试从加密数据中提取 MP4...")
            
            # 搜索 MP4 box 标记
            for marker in [b'free', b'mdat', b'moov', b'ftyp']:
                pos = data.find(marker)
                if pos > 4 and pos < 600000:  # 在前 600KB 内找到
                    try:
                        box_size = struct.unpack('>I', data[pos-4:pos])[0]
                        if 8 <= box_size <= len(data):
                            # 找到有效的 box，从这里开始提取
                            mp4_start = pos - 4
                            decrypted = bytearray(data[mp4_start:])
                            logger.info(f"从位置 {mp4_start} (0x{mp4_start:X}) 提取 MP4 数据（{marker.decode()} box）")
                            mp4_extracted = True
                            break
                    except:
                        pass
            
            # 方法 3: 尝试单字节 XOR 暴力破解（作为最后手段）
            if not mp4_extracted:
                logger.info("尝试单字节 XOR 暴力破解...")
                for test_key in range(256):
                    test_data = bytearray(data[:ENCRYPTED_HEADER_SIZE] if len(data) > ENCRYPTED_HEADER_SIZE else data)
                    for i in range(len(test_data)):
                        test_data[i] ^= test_key
                    
                    # 检查解密后是否是有效的视频文件头
                    if VideoDecryptor._is_valid_video_header(bytes(test_data[:16])):
                        detected_key = bytes([test_key])
                        decrypt_size = min(ENCRYPTED_HEADER_SIZE, len(data))
                        decrypted = bytearray(data)
                        for i in range(decrypt_size):
                            decrypted[i] ^= test_key
                        logger.info(f"找到解密密钥: 0x{test_key:02X}")
                        break
        
        if decrypted is None:
            return DecryptResult(
                success=False,
                error_message="无法找到正确的解密密钥",
                encryption_type=EncryptionType.UNKNOWN,
            )
        
        # 验证解密/提取结果
        # 对于微信视频号，文件可能以 free box 开始，这也是有效的
        if not VideoDecryptor._is_valid_video_header(bytes(decrypted[:16])):
            # 检查是否以 free/skip/wide box 开始（这些也是有效的 MP4）
            if len(decrypted) >= 8:
                box_type = decrypted[4:8]
                if box_type in [b'free', b'skip', b'wide', b'mdat']:
                    logger.info(f"文件以 {box_type.decode()} box 开始，这是有效的 MP4 格式")
                else:
                    return DecryptResult(
                        success=False,
                        error_message="解密后的文件头无效",
                        encryption_type=EncryptionType.XOR,
                    )
            else:
                return DecryptResult(
                    success=False,
                    error_message="解密后的文件头无效",
                    encryption_type=EncryptionType.XOR,
                )
        
        # 写入解密/提取后的文件
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(decrypted)
        except Exception as e:
            return DecryptResult(
                success=False,
                error_message=f"写入文件失败: {e}",
            )

        # 检查是否缺少 moov box（播放所需的元数据）
        # 有些视频可以通过 ffmpeg remux/faststart 修复
        has_moov = b'moov' in bytes(decrypted[:min(1024 * 1024, len(decrypted))])  # 在前 1MB 中搜索
        repair_info = None
        if not has_moov:
            logger.warning("视频文件缺少 moov box（元数据），尝试使用 ffmpeg 修复")

            repaired_path = output_path.with_suffix(output_path.suffix + '.repaired.mp4')
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',
                '-hide_banner',
                '-loglevel',
                'error',
                '-i',
                str(output_path),
                '-c',
                'copy',
                '-movflags',
                '+faststart',
                str(repaired_path),
            ]

            try:
                completed = subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if completed.returncode == 0 and repaired_path.exists() and repaired_path.stat().st_size > 0:
                    # 用修复后的文件替换输出
                    try:
                        output_path.unlink(missing_ok=True)
                    except TypeError:
                        # Python < 3.8 兼容
                        if output_path.exists():
                            output_path.unlink()
                    repaired_path.rename(output_path)
                    repair_info = {
                        'attempted': True,
                        'success': True,
                        'method': 'ffmpeg_faststart_remux',
                    }
                    logger.info("ffmpeg 修复成功")
                else:
                    repair_info = {
                        'attempted': True,
                        'success': False,
                        'method': 'ffmpeg_faststart_remux',
                        'stderr': (completed.stderr or '').strip()[:2000],
                        'returncode': completed.returncode,
                    }
                    logger.warning(f"ffmpeg 修复失败，returncode={completed.returncode}")
            except FileNotFoundError:
                repair_info = {
                    'attempted': True,
                    'success': False,
                    'method': 'ffmpeg_faststart_remux',
                    'error': 'ffmpeg_not_found',
                }
                logger.warning("ffmpeg 未安装或不在 PATH 中，无法修复")
            except subprocess.TimeoutExpired:
                repair_info = {
                    'attempted': True,
                    'success': False,
                    'method': 'ffmpeg_faststart_remux',
                    'error': 'timeout',
                }
                logger.warning("ffmpeg 修复超时")
            except Exception as e:
                repair_info = {
                    'attempted': True,
                    'success': False,
                    'method': 'ffmpeg_faststart_remux',
                    'error': str(e),
                }
                logger.exception("ffmpeg 修复异常")

            # 修复后再检查一次 moov
            try:
                with open(output_path, 'rb') as f:
                    head = f.read(1024 * 1024)
                has_moov = b'moov' in head
                if not has_moov:
                    # 仍然缺失 moov，返回失败但附带修复信息
                    return DecryptResult(
                        success=False,
                        error_message="视频文件已加密且缺少播放所需的元数据（moov box）",
                        encryption_type=EncryptionType.XOR,
                        additional_info={
                            'missing_moov': True,
                            'repair': repair_info,
                            'suggestion': "微信视频号使用了复杂的加密算法，目前无法自动解密。建议：\n"
                                         "1. 在微信中直接观看视频\n"
                                         "2. 使用专门的视频号下载工具（如 wechatVideoDownload: https://github.com/qiye45/wechatVideoDownload）\n"
                                         "3. 等待后续版本支持解密功能",
                        }
                    )
            except Exception:
                # 如果连复检都失败，按原逻辑返回缺 moov
                return DecryptResult(
                    success=False,
                    error_message="视频文件已加密且缺少播放所需的元数据（moov box）",
                    encryption_type=EncryptionType.XOR,
                    additional_info={
                        'missing_moov': True,
                        'repair': repair_info,
                    }
                )

        # 报告完成
        if progress_callback:
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    pass  # 暂时跳过
                else:
                    progress_callback(3, 3)  # 完成 (3/3)
            except Exception:
                pass

        return DecryptResult(
            success=True,
            output_path=str(output_path),
            encryption_type=EncryptionType.XOR,
            key=detected_key,
            additional_info={'repair': repair_info} if repair_info else None,
        )


# 兼容旧的函数式 API
def decrypt_video(input_path: str, output_path: Optional[str] = None) -> Tuple[bool, str]:
    """解密微信视频号视频（兼容旧 API）"""
    import asyncio
    
    if output_path is None:
        output_path = str(Path(input_path).with_suffix('.decrypted.mp4'))
    
    result = asyncio.run(VideoDecryptor.decrypt(input_path, output_path))
    
    if result.success:
        return True, result.output_path
    else:
        return False, result.error_message
