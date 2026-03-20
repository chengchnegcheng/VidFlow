"""
证书管理器属性测试

Property 4: Certificate Validity Detection
Property 5: Certificate Export Round-Trip
Validates: Requirements 3.1, 3.3, 3.4
"""

import pytest
from hypothesis import given, strategies as st, settings
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from src.core.channels.certificate_manager import CertificateManager
from src.core.channels.models import CertInfo, CertGenerateResult


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_cert_dir():
    """创建临时证书目录"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def cert_manager(temp_cert_dir):
    """创建证书管理器实例"""
    return CertificateManager(temp_cert_dir)


# ============================================================================
# Property 4: Certificate Validity Detection
# Validates: Requirements 3.1, 3.4
# ============================================================================

class TestCertificateValidityDetection:
    """
    Property 4: Certificate Validity Detection

    For any certificate state (missing, expired, valid), the
    CertificateManager.is_cert_valid() function should correctly identify
    the state. A newly generated certificate should always be valid.

    **Feature: weixin-channels-download, Property 4: Certificate Validity Detection**
    **Validates: Requirements 3.1, 3.4**
    """

    def test_missing_cert_is_invalid(self, cert_manager):
        """缺失的证书应该被检测为无效"""
        assert cert_manager.is_cert_valid() is False

        cert_info = cert_manager.get_cert_info()
        assert cert_info.exists is False
        assert cert_info.valid is False

    def test_newly_generated_cert_is_valid(self, cert_manager):
        """新生成的证书应该是有效的"""
        # 生成证书
        result = cert_manager.generate_ca_cert()
        assert result.success is True

        # 验证证书有效
        assert cert_manager.is_cert_valid() is True

        cert_info = cert_manager.get_cert_info()
        assert cert_info.exists is True
        assert cert_info.valid is True
        assert cert_info.expires_at is not None
        assert cert_info.fingerprint is not None

    def test_cert_info_contains_expiry_date(self, cert_manager):
        """证书信息应该包含过期日期"""
        cert_manager.generate_ca_cert()

        cert_info = cert_manager.get_cert_info()
        assert cert_info.expires_at is not None

        # 过期日期应该在未来
        assert cert_info.expires_at > datetime.now()

        # 过期日期应该大约在 3 年后
        expected_expiry = datetime.now() + timedelta(days=365 * 3)
        delta = abs((cert_info.expires_at - expected_expiry).days)
        assert delta < 2  # 允许 1 天误差

    def test_cert_info_contains_fingerprint(self, cert_manager):
        """证书信息应该包含指纹"""
        cert_manager.generate_ca_cert()

        cert_info = cert_manager.get_cert_info()
        assert cert_info.fingerprint is not None
        assert len(cert_info.fingerprint) > 0
        # 指纹格式应该是 XX:XX:XX...
        assert ":" in cert_info.fingerprint

    def test_deleted_cert_is_invalid(self, cert_manager):
        """删除后的证书应该被检测为无效"""
        # 先生成证书
        cert_manager.generate_ca_cert()
        assert cert_manager.is_cert_valid() is True

        # 删除证书
        cert_manager.delete_cert()

        # 验证证书无效
        assert cert_manager.is_cert_valid() is False

    def test_regenerate_cert_always_valid(self, cert_manager):
        """多次重新生成证书，每次都应该有效"""
        for _ in range(5):
            result = cert_manager.generate_ca_cert()
            assert result.success is True
            assert cert_manager.is_cert_valid() is True


# ============================================================================
# Property 5: Certificate Export Round-Trip
# Validates: Requirements 3.3
# ============================================================================

class TestCertificateExportRoundTrip:
    """
    Property 5: Certificate Export Round-Trip

    For any valid CA certificate, exporting it to a path and then reading
    from that path should produce identical certificate content.

    **Feature: weixin-channels-download, Property 5: Certificate Export Round-Trip**
    **Validates: Requirements 3.3**
    """

    def test_export_and_read_produces_identical_content(self, cert_manager, temp_cert_dir):
        """导出并读取证书应该产生相同的内容"""
        # 生成证书
        cert_manager.generate_ca_cert()

        # 获取原始内容
        original_content = cert_manager.get_cert_content()
        assert original_content is not None

        # 导出到新位置
        export_path = temp_cert_dir / "exported_cert.pem"
        success = cert_manager.export_cert(export_path)
        assert success is True

        # 读取导出的内容
        with open(export_path, "rb") as f:
            exported_content = f.read()

        # 验证内容相同
        assert original_content == exported_content

    def test_export_to_nested_directory(self, cert_manager, temp_cert_dir):
        """导出到嵌套目录应该自动创建目录"""
        cert_manager.generate_ca_cert()

        # 导出到嵌套目录
        export_path = temp_cert_dir / "nested" / "deep" / "cert.pem"
        success = cert_manager.export_cert(export_path)

        assert success is True
        assert export_path.exists()

    def test_export_without_cert_fails(self, cert_manager, temp_cert_dir):
        """没有证书时导出应该失败"""
        export_path = temp_cert_dir / "exported_cert.pem"
        success = cert_manager.export_cert(export_path)

        assert success is False
        assert not export_path.exists()

    def test_export_with_various_filenames(self, cert_manager, temp_cert_dir):
        """使用各种文件名导出应该都能成功"""
        cert_manager.generate_ca_cert()

        filenames = ["cert", "my_cert", "test-cert", "cert123", "a"]
        for filename in filenames:
            export_path = temp_cert_dir / f"{filename}.pem"
            success = cert_manager.export_cert(export_path)

            assert success is True
            assert export_path.exists()

            # 验证内容
            original = cert_manager.get_cert_content()
            with open(export_path, "rb") as f:
                exported = f.read()
            assert original == exported


# ============================================================================
# Additional Unit Tests
# ============================================================================

class TestCertificateGeneration:
    """证书生成单元测试"""

    def test_generate_creates_both_files(self, cert_manager):
        """生成证书应该创建证书和私钥两个文件"""
        result = cert_manager.generate_ca_cert()

        assert result.success is True
        assert cert_manager.ca_cert_path.exists()
        assert cert_manager.ca_key_path.exists()

    def test_generate_result_contains_path(self, cert_manager):
        """生成结果应该包含证书路径"""
        result = cert_manager.generate_ca_cert()

        assert result.success is True
        assert result.cert_path is not None
        assert Path(result.cert_path).exists()

    def test_cert_is_pem_format(self, cert_manager):
        """证书应该是 PEM 格式"""
        cert_manager.generate_ca_cert()

        content = cert_manager.get_cert_content()
        assert content is not None
        assert b"-----BEGIN CERTIFICATE-----" in content
        assert b"-----END CERTIFICATE-----" in content


class TestCertificateDeletion:
    """证书删除测试"""

    def test_delete_removes_both_files(self, cert_manager):
        """删除应该移除证书和私钥"""
        cert_manager.generate_ca_cert()

        assert cert_manager.ca_cert_path.exists()
        assert cert_manager.ca_key_path.exists()

        cert_manager.delete_cert()

        assert not cert_manager.ca_cert_path.exists()
        assert not cert_manager.ca_key_path.exists()

    def test_delete_nonexistent_succeeds(self, cert_manager):
        """删除不存在的证书应该成功"""
        result = cert_manager.delete_cert()
        assert result is True


class TestInstallInstructions:
    """安装说明测试"""

    def test_instructions_contain_platforms(self, cert_manager):
        """安装说明应该包含各平台"""
        instructions = cert_manager.get_install_instructions()

        assert "Windows" in instructions
        assert "macOS" in instructions
        assert "iOS" in instructions
        assert "Android" in instructions

    def test_instructions_not_empty(self, cert_manager):
        """安装说明不应该为空"""
        instructions = cert_manager.get_install_instructions()
        assert len(instructions) > 100
