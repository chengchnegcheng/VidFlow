"""
视频解密器属性测试

Property 8: Encryption Detection and Decryption Round-Trip
Validates: Requirements 5.1, 5.2, 5.3
"""

import pytest
from hypothesis import given, strategies as st, settings
import tempfile
import shutil
from pathlib import Path
import asyncio

from src.core.channels.video_decryptor import VideoDecryptor, VIDEO_MAGIC_NUMBERS
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


# ============================================================================
# Test Data
# ============================================================================

# 有效的 MP4 文件头
VALID_MP4_HEADER = b'\x00\x00\x00\x1c\x66\x74\x79\x70\x69\x73\x6f\x6d\x00\x00\x02\x00'

# 有效的 WebM 文件头
VALID_WEBM_HEADER = b'\x1a\x45\xdf\xa3\x01\x00\x00\x00\x00\x00\x00\x1f'

# 有效的 FLV 文件头
VALID_FLV_HEADER = b'\x46\x4c\x56\x01\x05\x00\x00\x00\x09\x00\x00\x00\x00'


# ============================================================================
# Property 8: Encryption Detection and Decryption Round-Trip
# Validates: Requirements 5.1, 5.2, 5.3
# ============================================================================

class TestEncryptionDetectionAndDecryption:
    """
    Property 8: Encryption Detection and Decryption Round-Trip

    For any encrypted video file with known encryption type, detecting the
    encryption type should return the correct type. For XOR-encrypted files,
    decrypting with the correct key should produce a valid video file.

    **Feature: weixin-channels-download, Property 8: Encryption Detection and Decryption Round-Trip**
    **Validates: Requirements 5.1, 5.2, 5.3**
    """

    def test_detect_unencrypted_mp4(self, temp_dir):
        """检测未加密的 MP4 文件"""
        # 创建未加密的 MP4 文件
        file_path = temp_dir / "test.mp4"
        with open(file_path, 'wb') as f:
            f.write(VALID_MP4_HEADER + b'\x00' * 100)

        encryption_type = VideoDecryptor.detect_encryption(file_path)
        assert encryption_type == EncryptionType.NONE

    def test_detect_unencrypted_webm(self, temp_dir):
        """检测未加密的 WebM 文件"""
        file_path = temp_dir / "test.webm"
        with open(file_path, 'wb') as f:
            f.write(VALID_WEBM_HEADER + b'\x00' * 100)

        encryption_type = VideoDecryptor.detect_encryption(file_path)
        assert encryption_type == EncryptionType.NONE

    def test_detect_xor_encrypted_file(self, temp_dir):
        """检测 XOR 加密的文件"""
        # 创建 XOR 加密的文件
        key = bytes([0xA3])
        encrypted_header = VideoDecryptor.encrypt_xor(VALID_MP4_HEADER, key)

        file_path = temp_dir / "encrypted.mp4"
        with open(file_path, 'wb') as f:
            f.write(encrypted_header + b'\x00' * 100)

        encryption_type = VideoDecryptor.detect_encryption(file_path)
        assert encryption_type == EncryptionType.XOR

    def test_detect_nonexistent_file(self):
        """检测不存在的文件"""
        encryption_type = VideoDecryptor.detect_encryption(Path("/nonexistent/file.mp4"))
        assert encryption_type == EncryptionType.UNKNOWN

    def test_detect_empty_file(self, temp_dir):
        """检测空文件"""
        file_path = temp_dir / "empty.mp4"
        file_path.touch()

        encryption_type = VideoDecryptor.detect_encryption(file_path)
        assert encryption_type == EncryptionType.UNKNOWN

    @pytest.mark.asyncio
    async def test_xor_decrypt_round_trip(self, temp_dir):
        """XOR 加密解密往返测试"""
        # 原始数据
        original_data = VALID_MP4_HEADER + b'\x00' * 1000
        key = bytes([0xA3])

        # 加密
        encrypted_data = VideoDecryptor.encrypt_xor(original_data, key)

        # 写入加密文件
        encrypted_path = temp_dir / "encrypted.mp4"
        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)

        # 解密
        decrypted_path = temp_dir / "decrypted.mp4"
        result = await VideoDecryptor.decrypt(
            encrypted_path,
            decrypted_path,
            EncryptionType.XOR,
            key
        )

        assert result.success is True
        assert decrypted_path.exists()

        # 验证解密后的内容
        with open(decrypted_path, 'rb') as f:
            decrypted_data = f.read()

        assert decrypted_data == original_data

    @pytest.mark.asyncio
    async def test_decrypt_with_auto_key_detection(self, temp_dir):
        """自动检测密钥的解密测试"""
        # 原始数据
        original_data = VALID_MP4_HEADER + b'\x00' * 500
        key = bytes([0xA3])

        # 加密
        encrypted_data = VideoDecryptor.encrypt_xor(original_data, key)

        # 写入加密文件
        encrypted_path = temp_dir / "encrypted.mp4"
        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)

        # 解密（不提供密钥，自动检测）
        decrypted_path = temp_dir / "decrypted.mp4"
        result = await VideoDecryptor.decrypt(
            encrypted_path,
            decrypted_path,
            EncryptionType.XOR,
            key=None  # 自动检测
        )

        assert result.success is True

        # 验证解密后的内容
        with open(decrypted_path, 'rb') as f:
            decrypted_data = f.read()

        assert decrypted_data == original_data

    @pytest.mark.asyncio
    async def test_decrypt_unencrypted_file(self, temp_dir):
        """解密未加密的文件（应该直接复制）"""
        # 创建未加密文件
        original_data = VALID_MP4_HEADER + b'\x00' * 100
        input_path = temp_dir / "original.mp4"
        with open(input_path, 'wb') as f:
            f.write(original_data)

        # "解密"
        output_path = temp_dir / "output.mp4"
        result = await VideoDecryptor.decrypt(
            input_path,
            output_path,
            EncryptionType.NONE
        )

        assert result.success is True
        assert output_path.exists()

        with open(output_path, 'rb') as f:
            output_data = f.read()

        assert output_data == original_data

    @pytest.mark.asyncio
    async def test_decrypt_nonexistent_file(self, temp_dir):
        """解密不存在的文件"""
        result = await VideoDecryptor.decrypt(
            temp_dir / "nonexistent.mp4",
            temp_dir / "output.mp4",
            EncryptionType.XOR
        )

        assert result.success is False
        assert "不存在" in result.error_message

    @pytest.mark.asyncio
    async def test_decrypt_with_progress_callback(self, temp_dir):
        """带进度回调的解密测试"""
        # 创建较大的加密文件
        original_data = VALID_MP4_HEADER + b'\x00' * 10000
        key = bytes([0xA3])
        encrypted_data = VideoDecryptor.encrypt_xor(original_data, key)

        encrypted_path = temp_dir / "encrypted.mp4"
        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)

        # 记录进度回调
        progress_calls = []

        async def progress_callback(processed: int, total: int):
            progress_calls.append((processed, total))

        # 解密
        decrypted_path = temp_dir / "decrypted.mp4"
        result = await VideoDecryptor.decrypt(
            encrypted_path,
            decrypted_path,
            EncryptionType.XOR,
            key,
            progress_callback
        )

        assert result.success is True
        assert len(progress_calls) > 0

        # 验证进度值
        for processed, total in progress_calls:
            assert 0 <= processed <= total
            assert total == len(encrypted_data)


# ============================================================================
# XOR Encryption/Decryption Tests
# ============================================================================

class TestXOREncryption:
    """XOR 加密/解密单元测试"""

    def test_xor_single_byte_key(self):
        """单字节密钥 XOR"""
        data = b"Hello, World!"
        key = bytes([0xA3])

        encrypted = VideoDecryptor.encrypt_xor(data, key)
        decrypted = VideoDecryptor.encrypt_xor(encrypted, key)

        assert decrypted == data

    def test_xor_multi_byte_key(self):
        """多字节密钥 XOR"""
        data = b"Hello, World!"
        key = bytes([0xA3, 0x5A, 0xFF])

        encrypted = VideoDecryptor.encrypt_xor(data, key)
        decrypted = VideoDecryptor.encrypt_xor(encrypted, key)

        assert decrypted == data

    def test_xor_empty_data(self):
        """空数据 XOR"""
        data = b""
        key = bytes([0xA3])

        encrypted = VideoDecryptor.encrypt_xor(data, key)
        assert encrypted == b""

    def test_xor_empty_key(self):
        """空密钥 XOR（应该返回原数据）"""
        data = b"Hello, World!"
        key = b""

        result = VideoDecryptor.encrypt_xor(data, key)
        assert result == data

    @given(
        data=st.binary(min_size=1, max_size=1000),
        key=st.binary(min_size=1, max_size=16)
    )
    @settings(max_examples=100)
    def test_xor_round_trip_property(self, data, key):
        """XOR 往返属性：加密后解密应该得到原数据"""
        encrypted = VideoDecryptor.encrypt_xor(data, key)
        decrypted = VideoDecryptor.encrypt_xor(encrypted, key)

        assert decrypted == data


# ============================================================================
# Key Extraction Tests
# ============================================================================

class TestKeyExtraction:
    """密钥提取测试"""

    def test_extract_hex_key_from_url(self):
        """从 URL 提取十六进制密钥"""
        url = "https://example.com/video?key=a3b5c7"
        key = VideoDecryptor.extract_key_from_url(url)

        assert key == bytes.fromhex("a3b5c7")

    def test_extract_string_key_from_url(self):
        """从 URL 提取字符串密钥"""
        url = "https://example.com/video?key=notahexkey"
        key = VideoDecryptor.extract_key_from_url(url)

        assert key == b"notahexkey"

    def test_extract_key_alternative_param(self):
        """从其他参数名提取密钥"""
        url = "https://example.com/video?decryptkey=ff00"
        key = VideoDecryptor.extract_key_from_url(url)

        assert key == bytes.fromhex("ff00")

    def test_extract_key_no_param(self):
        """没有密钥参数"""
        url = "https://example.com/video?vid=123"
        key = VideoDecryptor.extract_key_from_url(url)

        assert key is None

    def test_extract_key_empty_url(self):
        """空 URL"""
        assert VideoDecryptor.extract_key_from_url("") is None
        assert VideoDecryptor.extract_key_from_url(None) is None


# ============================================================================
# Video Header Detection Tests
# ============================================================================

class TestVideoHeaderDetection:
    """视频文件头检测测试"""

    def test_valid_mp4_header(self):
        """有效的 MP4 文件头"""
        assert VideoDecryptor._is_valid_video_header(VALID_MP4_HEADER) is True

    def test_valid_webm_header(self):
        """有效的 WebM 文件头"""
        assert VideoDecryptor._is_valid_video_header(VALID_WEBM_HEADER) is True

    def test_valid_flv_header(self):
        """有效的 FLV 文件头"""
        assert VideoDecryptor._is_valid_video_header(VALID_FLV_HEADER) is True

    def test_invalid_header(self):
        """无效的文件头"""
        assert VideoDecryptor._is_valid_video_header(b'\x00\x00\x00\x00') is False
        assert VideoDecryptor._is_valid_video_header(b'random') is False

    def test_short_header(self):
        """过短的文件头"""
        assert VideoDecryptor._is_valid_video_header(b'\x00\x00') is False
        assert VideoDecryptor._is_valid_video_header(b'') is False
