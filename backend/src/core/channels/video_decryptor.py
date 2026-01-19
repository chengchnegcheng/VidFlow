"""
微信视频号视频解密器

微信视频号下载的视频是加密的，前 131072 字节（0x20000）与固定 key 做异或。
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.parse import urlparse, parse_qs

from .models import EncryptionType, DecryptResult

logger = logging.getLogger(__name__)

# 加密区域大小
ENCRYPTED_SIZE = 0x20000  # 131072 bytes

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
        except Exception:
            return EncryptionType.UNKNOWN
        
        if len(header) < 8:
            return EncryptionType.UNKNOWN
        
        # 检查是否是有效的视频文件头
        if VideoDecryptor._is_valid_video_header(header):
            return EncryptionType.NONE
        
        # 尝试检测 XOR 加密
        # 假设原始文件是 MP4，第 4-7 字节应该是 "ftyp"
        for key_byte in range(256):
            test_header = bytes([b ^ key_byte for b in header[:8]])
            if test_header[4:8] == b'ftyp':
                return EncryptionType.XOR
        
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
        
        # MPEG-TS
        if header[0] == 0x47:  # TS sync byte
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
            
            # 常见的密钥参数名
            key_params = ['key', 'decryptkey', 'decodekey', 'k']
            
            for param in key_params:
                if param in params:
                    key_str = params[param][0]
                    # 尝试解析为十六进制
                    try:
                        return bytes.fromhex(key_str)
                    except ValueError:
                        # 不是十六进制，作为字符串处理
                        return key_str.encode()
            
            return None
        except Exception:
            return None
    
    @staticmethod
    async def decrypt(
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        key: Optional[bytes] = None,
    ) -> DecryptResult:
        """解密视频文件
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            key: 解密密钥，如果为 None 则自动检测
            
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
        
        # 尝试解密
        decrypted = None
        detected_key = None
        
        if key:
            # 使用提供的密钥
            decrypt_size = min(ENCRYPTED_SIZE, len(data))
            decrypted = bytearray(data)
            key_len = len(key)
            for i in range(decrypt_size):
                decrypted[i] ^= key[i % key_len]
            detected_key = key
        else:
            # 自动检测密钥（单字节 XOR）
            for test_key in range(256):
                test_header = bytes([b ^ test_key for b in data[:8]])
                if test_header[4:8] == b'ftyp':
                    detected_key = bytes([test_key])
                    decrypt_size = min(ENCRYPTED_SIZE, len(data))
                    decrypted = bytearray(data)
                    for i in range(decrypt_size):
                        decrypted[i] ^= test_key
                    break
        
        if decrypted is None:
            return DecryptResult(
                success=False,
                error_message="无法找到正确的解密密钥",
                encryption_type=EncryptionType.UNKNOWN,
            )
        
        # 验证解密结果
        if not VideoDecryptor._is_valid_video_header(bytes(decrypted[:16])):
            return DecryptResult(
                success=False,
                error_message="解密后的文件头无效",
                encryption_type=EncryptionType.XOR,
            )
        
        # 写入解密后的文件
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(decrypted)
            
            return DecryptResult(
                success=True,
                output_path=str(output_path),
                encryption_type=EncryptionType.XOR,
                key=detected_key,
            )
        except Exception as e:
            return DecryptResult(
                success=False,
                error_message=f"写入文件失败: {e}",
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


def find_wechat_video_cache() -> Optional[Path]:
    """查找微信视频缓存目录"""
    possible_paths = [
        Path(os.environ.get('USERPROFILE', '')) / 'Documents' / 'WeChat Files',
        Path(os.environ.get('APPDATA', '')) / 'Tencent' / 'WeChat',
        Path('D:/WeChat Files'),
        Path('E:/WeChat Files'),
    ]
    
    for base_path in possible_paths:
        if base_path.exists():
            for user_dir in base_path.iterdir():
                if user_dir.is_dir():
                    video_cache = user_dir / 'FileStorage' / 'Video'
                    if video_cache.exists():
                        return video_cache
    
    return None


def list_cached_videos(cache_dir: Optional[Path] = None) -> list:
    """列出缓存的视频文件"""
    if cache_dir is None:
        cache_dir = find_wechat_video_cache()
    
    if cache_dir is None or not cache_dir.exists():
        return []
    
    videos = []
    for file in cache_dir.rglob('*'):
        if file.is_file() and file.suffix.lower() in ['.mp4', '.video', '']:
            if file.stat().st_size > 100 * 1024:
                videos.append({
                    'path': str(file),
                    'name': file.name,
                    'size': file.stat().st_size,
                    'modified': file.stat().st_mtime,
                })
    
    videos.sort(key=lambda x: x['modified'], reverse=True)
    return videos
